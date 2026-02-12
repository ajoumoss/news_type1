import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re
import html

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

def search_naver_news(query, display=100, start=1, sort='date'):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": display, "start": start, "sort": sort}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        items = response.json().get('items', [])
        # 초기 단계에서 인코딩 수정
        for item in items:
            item['title'] = html.unescape(item['title']).replace('<b>', '').replace('</b>', '')
            item['description'] = html.unescape(item['description']).replace('<b>', '').replace('</b>', '')
        return items
    return []

def extract_article_details(url):
    details = {"content": "", "reporter": "정보 없음", "company": "정보 없음", "mentions": ""}
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return details
        
        # HTML 엔티티 변환을 위해 BeautifulSoup 사용 전 unescape 고려 가능하나 soup이 처리해줌
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 네이버 뉴스 전용 고정밀 추출
        if "news.naver.com" in url:
            # 언론사명 추출
            company_tag = soup.select_one('.media_end_head_top_logo img') or soup.select_one('meta[property="og:article:author"]')
            if company_tag:
                details["company"] = company_tag.get('title') or company_tag.get('content')
            
            # 기자명 추출
            journalist_tag = soup.select_one('.media_end_head_journalist_name')
            if journalist_tag:
                details["reporter"] = journalist_tag.get_text().strip()
            else:
                # 기자가 없는 경우 '매일신문 | 네이버' 처럼 섞여 들어가는 것 방지
                # og:description 이나 다른 태그에서 기자명 찾기
                author_tag = soup.select_one('meta[name="author"]')
                if author_tag:
                    author_val = author_tag.get('content', '')
                    if " | 네이버" in author_val:
                        details["reporter"] = "정보 없음" # 언론사 이름이 섞인 것이므로 무시
                    else:
                        details["reporter"] = author_val.strip()

        # 2. 일반 언론사 (범용)
        if details["company"] == "정보 없음":
            company = (soup.select_one('meta[property="og:site_name"]') or 
                       soup.select_one('meta[name="twitter:site"]') or 
                       soup.select_one('meta[name="publisher"]'))
            if company:
                details["company"] = company.get('content', '').strip()
        
        if details["reporter"] == "정보 없음":
            reporter = (soup.select_one('meta[name="author"]') or 
                        soup.select_one('meta[property="og:article:author"]') or 
                        soup.select_one('meta[name="dable:author"]'))
            if reporter:
                rep_val = reporter.get('content', '').strip()
                if " | " not in rep_val and len(rep_val) < 10: 
                    details["reporter"] = rep_val

        # 3. 본문 추출 및 본문 내 기자명 2차 검색
        content_tag = (soup.select_one('#newsct_article') or 
                       soup.select_one('#articleBodyContents') or 
                       soup.select_one('article') or 
                       soup.select_one('.article_body') or 
                       soup.select_one('#article_content') or
                       soup.select_one('.news_body_area') or
                       soup.select_one('#news_body_area') or
                       soup.select_one('.article-body') or
                       soup.select_one('.article_view'))
        
        if content_tag:
            for s in content_tag(['script', 'style', 'nav', 'footer', 'header']): s.decompose()
            text_content = html.unescape(content_tag.get_text('\n', strip=True))
            details["content"] = text_content
            
            # 본문 내에서 기자명 패턴 찾기 (메타데이터 실패 시)
            if details["reporter"] == "정보 없음":
                # 패턴 1: [서울=뉴스핌] 윤창빈 기자 = ...
                # 패턴 2: 윤창빈 기자 (email)
                # 패턴 3: 기자 = 윤창빈
                # 패턴 4: 윤창빈기자
                patterns = [
                    r'([가-힣]{2,4})\s*기자\s*=',
                    r'([가-힣]{2,4})\s*기자\s*\(',
                    r'기자\s*=\s*([가-힣]{2,4})',
                    r'([가-힣]{2,4})\s*기자(?!\w)',
                    r'\[.*?\]\s*([가-힣]{2,4})\s*기자'
                ]
                # 기사 앞쪽 500자 이내에서 검색
                search_text = text_content[:500]
                for p in patterns:
                    match = re.search(p, search_text)
                    if match:
                        name = match.group(1).strip()
                        if 2 <= len(name) <= 4: # 한국인 이름 길이 체크
                            details["reporter"] = f"{name} 기자"
                            break

        # 4. 언급 요약 (사용 안 함)
        details["mentions"] = ""
            
    except Exception as e:
        print(f"Error extracting details from {url}: {e}")
        
    return details

def summarize_mentions(text):
    return ""

def is_relevant_article(item, start_date=None, end_date=None, content=None):
    title = item.get('title', '').replace('<b>', '').replace('</b>', '')
    description = item.get('description', '').replace('<b>', '').replace('</b>', '')
    
    # 제목 + 설명 + (선택적) 본문 결합
    combined_text = title + " " + description
    if content:
        combined_text += " " + content
    
    # 1. 문체부/문체위 관련 키워드 확인
    # 0. 포토뉴스 및 초단문 기사 필터링 (단순 홍보/사진 기사 제외)
    if any(title.startswith(prefix) for prefix in ['[포토]', '[사진]', '[Photo]', '포토]', '사진]']):
        return False
        
    if content and len(content) < 80:
        return False

    # 0-0. 연예 뉴스 필터링 (entertain.naver.com)
    if 'entertain.naver.com' in item.get('link', ''):
        return False


    # 0-1. 영화 '슈가' 단순 홍보 기사 필터링 (강제 제외)
    # '슈가'가 포함되면서 동시에 배우 이름이나 영화 관련 단어가 있으면 제외
    if '슈가' in title:
        movie_keywords = ['최지우', '시사회', '개봉', '아역', '촬영', '케미', '스크린', '극장', '예고편', '포스터']
        if any(mk in title for mk in movie_keywords):
            return False

    # 1. 문체부/문체위 관련 키워드 확인
    general_keywords = ['1형 당뇨', '1형당뇨']
    strong_keywords = ['소아당뇨', '췌장장애']
    all_keywords = general_keywords + strong_keywords
    
    # 제목에 키워드가 있으면 무조건 통과
    for k in all_keywords:
        if k in title:
            return True
            
    # if not in title, check other filters
    # ...
        
    # 본문 필터링 (하이브리드 방식)
    if content:
        # 강력 키워드(소아당뇨, 췌장장애)는 1번만 나와도 통과
        for k in strong_keywords:
            if k in content:
                return True
                
        # 일반 키워드(1형 당뇨)는 2번 이상 나와야 통과 (단순 언급 방지)
        for k in general_keywords:
            if content.count(k) >= 2:
                return True

    # 3. 기간 필터링
    try:
        pub_dt = datetime.strptime(item.get('pubDate', ''), "%a, %d %b %Y %H:%M:%S %z")
        if start_date and pub_dt < start_date: return False
        if end_date and pub_dt > end_date: return False
    except: pass
    
    return False

def filter_articles(items, start_date=None, end_date=None):
    return [item for item in items if is_relevant_article(item, start_date, end_date)]
