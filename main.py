import sys
from scraper import search_naver_news, is_relevant_article, extract_article_details
from notion_integrator import add_article_to_notion, update_article_in_notion, get_existing_article_page_id, check_database_exists, check_article_exists_by_title
import time
from datetime import datetime, timezone, timedelta

def run_crawler(hours=24):
    print(f"[{datetime.now()}] 뉴스 크롤러 실행 (대상: 최근 {hours}시간)")
    
    # KST 설정
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    start_date = now - timedelta(hours=hours)

    if not check_database_exists():
        print("Notion 데이터베이스에 접근할 수 없습니다. ID와 토큰을 확인하세요.")
        return

    queries = ["1형 당뇨", "1형당뇨", "소아당뇨"]
    all_articles = []
    
    # 1. 키워드별 뉴스 검색
    for query in queries:
        print(f"'{query}' 검색 중...")
        for start_idx in range(1, 201, 100):
            articles = search_naver_news(query, start=start_idx)
            if not articles: break
            all_articles.extend(articles)
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
            if pub_dt >= start_date:
                recent_articles.append(a)
        except:
            pass
            
    print(f"검색된 기사: {len(unique_articles)}개 -> {len(recent_articles)}개 ({hours}시간 이내)")

    count_new = 0
    count_skipped = 0
    
    from classifier import classify_article_llm, classify_category_keyword, classify_type_keyword, llm_classifier
    
    processed_titles = []
    
    for i, a in enumerate(recent_articles):
        link = a['link']
        title = a['title']
        
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
        
        if not is_relevant_article(a, content=details['content']):
            print(" -> 관련 없는 기사로 판단되어 건너뜁니다.")
            continue
            
        # [분류]
        category, news_type = classify_article_llm(title, details['content'])
        
        if not category or not news_type:
            print(" -> LLM 분류 실패, 키워드 분류 시도...")
            full_text = f"{title} {details['content']}"
            category = classify_category_keyword(full_text)
            news_type = classify_type_keyword(full_text)
        
        print(f" -> 분류: {category} / {news_type}")
        
        success = add_article_to_notion(
            title=title, link=link, date=a['pubDate'], description=a['description'],
            category=category, type=news_type, press=details['company'],
            full_content=details['content'], mentions=details['mentions']
        )
        if success: count_new += 1
        
        time.sleep(0.5)
            
    print(f"작업 완료! 신규: {count_new}개, 중복/건너뜀: {count_skipped}개")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
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
