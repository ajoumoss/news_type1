
from llm_classifier import LLMClassifier

# Initialize LLM Classifier once
llm_classifier = LLMClassifier()

def classify_article_llm(title, content):
    """
    Tries to classify using LLM. Returns (category, type) tuple or None if failed.
    """
    if llm_classifier.client:
        result = llm_classifier.classify_article(title, content)
        if result:
            return result.get("category", "기타"), result.get("type", "기타")
    return None, None

def classify_category_keyword(text):
    """
    Fallback: Classifies text into Culture (문화), Sports (체육), Tourism (관광), or Other (기타).
    """
    text = text.lower()
    
    # Tourism keywords
    tourism_keywords = ['관광', '여행', '투어', '숙박', '호텔', '축제', '유커', '방한', '비자', '면세']
    if any(k in text for k in tourism_keywords):
        return "관광"
        
    # Sports keywords
    sports_keywords = ['체육', '스포츠', '경기', '선수', '올림픽', '월드컵', '축구', '야구', '배구', '농구', '팀', '리그']
    if any(k in text for k in sports_keywords):
        return "체육"
        
    # Culture keywords - broad, so check last
    culture_keywords = ['문화', '예술', '공연', '전시', '영화', '음악', 'K-POP', '한류', '콘텐츠', '게임', '웹툰', '출판', '도서']
    if any(k in text for k in culture_keywords):
        return "문화"
        
    return "기타"

def classify_type_keyword(text):
    """
    Fallback: Classifies text into Political (정쟁), Policy (정책), Promotion (홍보), Society (사회), or Other (기타).
    """
    text = text.lower()
    
    # Political keywords - prioritize these
    political_keywords = ['국회', '의원', '정당', '여야', '비판', '논란', '의혹', '감사', '질타', '공방', '사퇴', '해임', '규탄']
    if any(k in text for k in political_keywords):
        return "정쟁"
        
    # Policy keywords
    policy_keywords = ['정책', '발표', '계획', '지원', '육성', '조성', '개정', '법안', '시행', '제도', '예산', '국비', '공모', '선정']
    if any(k in text for k in policy_keywords):
        return "정책"
    
    # Promotion keywords
    promotion_keywords = ['개최', '이벤트', '참여', '모집', '홍보', '출시', '공개', '오픈', '기념', '축하']
    if any(k in text for k in promotion_keywords):
        return "홍보"

    # Social keywords - general news
    society_keywords = ['사회', '이슈', '사건', '사고', '피해', '불만', '갈등']
    if any(k in text for k in society_keywords):
        return "사회"
        
    return "기타"

def classify_category(text, title="", content=""): # Modified signature to support LLM if needed, though main.py needs update
    # This function is kept for backward compatibility if called with just text
    # But for LLM we need title and content separately.
    # We will update main.py to call a new function or handling this better.
    return classify_category_keyword(text)

def classify_type(text):
    return classify_type_keyword(text)
