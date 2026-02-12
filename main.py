import sys
import argparse
from scraper import search_naver_news, is_relevant_article, extract_article_details
from notion_integrator import add_article_to_notion, update_article_in_notion, get_existing_article_page_id, check_database_exists, check_article_exists_by_title
import time
from datetime import datetime, timezone, timedelta
from classifier import classify_category_keyword, classify_type_keyword, llm_classifier

def run_crawler(hours=24):
    print(f"[{datetime.now()}] 뉴스 크롤러 실행 (대상: 최근 {hours}시간)")
    
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    start_date = now - timedelta(hours=hours)
    end_date = None
    
    _execute_crawler(start_date, end_date, f"{hours}시간 이내")

def run_crawler_date(target_date_str):
    """
    target_date_str: 'YYYY-MM-DD'
    """
    print(f"[{datetime.now()}] 뉴스 크롤러 실행 (대상 날짜: {target_date_str})")
    
    kst = timezone(timedelta(hours=9))
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        start_date = datetime(target_date.year, target_date.month, target_date.day, tzinfo=kst)
        end_date = start_date + timedelta(days=1) - timedelta(seconds=1)
    except Exception as e:
        print(f"날짜 형식이 잘못되었습니다: {e}")
        return
    
    _execute_crawler(start_date, end_date, target_date_str)

def _execute_crawler(start_date, end_date, label):

    if not check_database_exists():
        print("Notion 데이터베이스에 접근할 수 없습니다. ID와 토큰을 확인하세요.")
        return

    queries = ["1형 당뇨", "1형당뇨", "소아당뇨", "췌장장애"]
    all_articles = []
    
    # 1. 키워드별 뉴스 검색
    for query in queries:
        print(f"'{query}' 검색 중...")
        for start_idx in range(1, 1001, 100):
            articles = search_naver_news(query, start=start_idx)
            if not articles: break
            all_articles.extend(articles)
            # If we reached articles older than start_date in 'date' sort, we could break.
            # But search_naver_news uses default sort (sim or date). main calls it without sort.
            # search_naver_news default is 'date'.
            last_dt = datetime.strptime(articles[-1]['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
            if last_dt < start_date:
                break
            time.sleep(0.3)

    # 1. 링크 기반 중복 제거
    seen_links = set()
    unique_articles = []
    for a in all_articles:
        if a['link'] not in seen_links:
            seen_links.add(a['link'])
            unique_articles.append(a)

    # 2. 날짜 필터링
    recent_articles = []
    for a in unique_articles:
        try:
            pub_dt = datetime.strptime(a.get('pubDate', ''), "%a, %d %b %Y %H:%M:%S %z")
            if end_date:
                if start_date <= pub_dt <= end_date:
                    recent_articles.append(a)
            elif pub_dt >= start_date:
                recent_articles.append(a)
        except:
            pass
            
    print(f"검색된 기사: {len(unique_articles)}개 -> {len(recent_articles)}개 ({label})")

    count_new = 0
    count_skipped = 0
    
    processed_titles = []
    
    for i, a in enumerate(recent_articles):
        link = a['link']
        title = a['title']
        
        # [중복 방지 0] 연예 뉴스 제외
        if "entertain.naver.com" in link:
             print(f"[{i+1}/{len(recent_articles)}] 연예 뉴스 제외 (entertain.naver.com): {title[:30]}...")
             count_skipped += 1
             continue

        print(f"[{i+1}/{len(recent_articles)}] 분석 중: {title[:30]}...")
        
        # [중복 방지 1] 제목으로 Notion 중복 확인 (Exact Match)
        if check_article_exists_by_title(title):
            print(" -> 이미 Notion에 존재하는 기사(제목 중복)입니다. 건너뜁니다.")
            count_skipped += 1
            continue
            
        # [중복 방지 2] LLM 의미 기반 중복 확인 (Semantic Match)
        is_duplicate, similar_title = llm_classifier.check_similarity(title, processed_titles)
        if is_duplicate:
            print(f" -> 유사한 기사가 이미 처리되었습니다. (유사 제목: {similar_title}) 건너뜁니다.")
            count_skipped += 1
            continue

        processed_titles.append(title) 

        details = extract_article_details(link)
        
        # Strict Relevance Check (Title or 2+ mentions) - already in scraper.is_relevant_article
        # But let's check classifier result too.
        
        if not is_relevant_article(a, content=details['content']):
            print(f" -> 관련 없는 기사로 판단되어 건너뜁니다. (키워드 부족 - 제목: '{title}', 본문길이: {len(details['content'])})")
            continue
            
        # [분류 및 요약]
        llm_result = llm_classifier.classify_article(title, details['content'])
        
        category = "기타"
        news_type = "기타"
        summary = ""
        
        if llm_result:
            category = llm_result.get("category", "기타")
            summary = llm_result.get("summary", "")
        else:
            print(" -> LLM 분류 실패, 키워드 분류 시도...")
            full_text = f"{title} {details['content']}"
            category = classify_category_keyword(full_text)
            
        # LLM이 "관련없음"으로 분류했으면 스킵
        if category == "관련없음":
             print(" -> LLM이 '관련없음'으로 분류했습니다. 건너뜁니다.")
             continue
        
        # 유형은 이제 사용하지 않으므로 '뉴스'로 통일 (또는 빈 값)
        news_type = "뉴스"
        
        print(f" -> 분류: {category}")
        print(f" -> 요약: {summary[:30]}...")
        
        success = add_article_to_notion(
            title=title, link=link, date=a['pubDate'], description=a['description'],
            category=category, type=news_type, press=details['company'],
            full_content=details['content'], mentions=details['mentions'],
            summary=summary
        )
        if success: count_new += 1
        
        time.sleep(0.5)
            
    print(f"작업 완료! 신규: {count_new}개, 중복/건너뜀: {count_skipped}개")

def run_crawler_year(year):
    print(f"=== {year}년도 전체 데이터 수집 시작 ===")
    
    # 1. 날짜 범위 설정
    kst = timezone(timedelta(hours=9))
    start_date = datetime(year, 1, 1, tzinfo=kst)
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=kst)
    
    if not check_database_exists():
        print("Notion 데이터베이스에 접근할 수 없습니다.")
        return

    queries = ["1형 당뇨", "1형당뇨", "소아당뇨", "췌장장애"]
    sort_methods = ["date", "sim"] # 최신순, 관련도순 교차 수집
    
    all_raw_articles = []
    
    # 2. 수집 (쿼리 x 정렬 x 페이지)
    for query in queries:
        for sort in sort_methods:
            print(f"검색 중: '{query}' (정렬: {sort})...")
            # 네이버 API 최대 1000개 제한
            for start_idx in range(1, 1001, 100):
                articles = search_naver_news(query, display=100, start=start_idx, sort=sort)
                if not articles: break
                
                # 날짜 체크 (date 정렬일 때 너무 과거로 가면 중단)
                if sort == 'date':
                    last_item_date = datetime.strptime(articles[-1]['pubDate'], "%a, %d %b %Y %H:%M:%S %z")
                    if last_item_date < start_date:
                        # 이번 페이지에 유효한게 있는지 확인 후 추가하고 break
                        valid_page = [a for a in articles if datetime.strptime(a['pubDate'], "%a, %d %b %Y %H:%M:%S %z") >= start_date]
                        all_raw_articles.extend(valid_page)
                        break
                
                all_raw_articles.extend(articles)
                time.sleep(0.1)

    # 3. 중복 제거 (링크 기준)
    seen_links = set()
    unique_articles = []
    for a in all_raw_articles:
        if a['link'] not in seen_links:
            seen_links.add(a['link'])
            unique_articles.append(a)
            
    # 4. 날짜 필터링 (정확히 해당 연도만)
    target_articles = []
    for a in unique_articles:
        try:
            pub_dt = datetime.strptime(a.get('pubDate', ''), "%a, %d %b %Y %H:%M:%S %z")
            if start_date <= pub_dt <= end_date:
                target_articles.append(a)
        except:
            pass
            
    print(f"수집 완료: 총 {len(unique_articles)}개 중 {year}년 기사 {len(target_articles)}개 확정")
    
    # 날짜순 정렬 (과거 -> 최신)
    target_articles.sort(key=lambda x: datetime.strptime(x['pubDate'], "%a, %d %b %Y %H:%M:%S %z"))

    count_new = 0
    count_skipped = 0
    processed_titles = [] # 이번 세션에서 처리한 제목들 (중복 방지용)
    
    # 5. 처리 및 저장
    total = len(target_articles)
    for i, a in enumerate(target_articles):
        link = a['link']
        title = a['title']
        
        if "entertain.naver.com" in link:
            print(f"[{i+1}/{total}] 연예 뉴스 제외: {title[:30]}...")
            count_skipped += 1
            continue

        print(f"[{i+1}/{total}] 처리 중 ({a['pubDate'][:16]}): {title[:30]}...")
        
        # Notion 중복 확인 (제목)
        if check_article_exists_by_title(title):
            print(" -> Notion 중복 (건너뜀)")
            count_skipped += 1
            continue
            
        # 세션 내 중복 확인 (제목)
        if title in processed_titles:
            print(" -> 세션 내 중복 (건너뜀)")
            count_skipped += 1
            continue
            
        # LLM 유사도 체크 (API 비용 절약을 위해, 리스트가 너무 길면 최근 50개만 비교 등 최적화 필요)
        # 1년치는 너무 많으므로, 최근 30개 정도와 비교하거나, 날짜가 비슷한 것끼리 비교해야 함.
        # 여기서는 간단히 패스하거나, 최근 처리한 20개와만 비교
        recent_titles = processed_titles[-20:] if len(processed_titles) > 20 else processed_titles
        is_duplicate, similar_title = llm_classifier.check_similarity(title, recent_titles)
        if is_duplicate:
            print(f" -> 유사 기사 존재 (유사: {similar_title})")
            count_skipped += 1
            continue

        details = extract_article_details(link)
        
        # 키워드 관련성 체크 (Scraper 로직 사용)
        if not is_relevant_article(a, content=details['content']):
            print(" -> 관련성 부족 (건너뜀)")
            continue
            
        # 분류 및 요약
        llm_result = llm_classifier.classify_article(title, details['content'])
        
        if llm_result:
            category = llm_result.get("category", "기타")
            summary = llm_result.get("summary", "")
        else:
            full_text = f"{title} {details['content']}"
            category = classify_category_keyword(full_text)
            summary = ""

        if category == "관련없음":
            print(" -> LLM 분류: 관련없음")
            continue
        
        # 유형은 이제 사용하지 않으므로 '뉴스'로 통일
        news_type = "뉴스"
        
        print(f" -> 등록: {category}")
        
        success = add_article_to_notion(
            title=title, link=link, date=a['pubDate'], description=a['description'],
            category=category, type=news_type, press=details['company'],
            full_content=details['content'], mentions=details['mentions'],
            summary=summary
        )
        if success:
            count_new += 1
            processed_titles.append(title)
        
        time.sleep(0.5)
        
    print(f"=== {year}년 처리 완료: 신규 {count_new}건, 중복/제외 {count_skipped}건 ===")

def main():
    parser = argparse.ArgumentParser(description="News Crawler for Type 1 Diabetes")
    parser.add_argument("--loop", action="store_true", help="Run in a loop every hour")
    parser.add_argument("--week", action="store_true", help="Scrape data for the last 7 days")
    parser.add_argument("--year", type=int, help="Scrape data for a specific year (e.g., 2026)")
    parser.add_argument("--date", type=str, help="Scrape data for a specific date (YYYY-MM-DD)")
    parser.add_argument("--hours", type=int, help="Scrape data for the last N hours")
    
    args = parser.parse_args()

    if args.date:
        run_crawler_date(args.date)
        return
    
    if args.year:
        run_crawler_year(args.year)
        return
    
    if args.hours:
        print(f"=== 최근 {args.hours}시간 데이터 수집 모드 시작 ===")
        run_crawler(hours=args.hours)
        return

    if args.week:
        print("=== 최근 7일(168시간) 데이터 수집 모드 시작 ===")
        run_crawler(hours=168)
        return

    if args.loop:
        print("=== 1시간 간격 연속 크롤링 모드 시작 ===")
        print("첫 실행은 최근 24시간 데이터를 수집하고, 이후에는 2시간 데이터를 수집합니다.")
        
        # 첫 실행: 24시간
        run_crawler(hours=24)
        
        while True:
            print("\n다음 실행까지 1시간 대기 중...", flush=True)
            time.sleep(3600)
            
            # 이후 실행: 2시간 (안전하게 중복 범위 포함)
            run_crawler(hours=2)
    else:
        # 단일 실행 (기본 24시간)
        run_crawler(hours=24)

if __name__ == "__main__":
    main()
