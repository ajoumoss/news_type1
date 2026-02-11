
import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class LLMClassifier:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("⚠️ GEMINI_API_KEY not found in .env")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.0-flash' # Using Flash for speed and cost effectiveness

    
    def classify_article(self, title, content):
        if not self.client:
            return None

        prompt = f"""
You are an expert news classifier for Type 1 Diabetes (1형 당뇨) news.
Analyze the following news article and classify it into "Category" and "Type".

[Article]
Title: {title}
Content Snippet: {content[:1000]}

[Classification Rules]
1. Category (Choose one):
   - 의학/연구 (Medical/Research): New treatments, clinical trials, medical studies, complications.
   - 정책/지원 (Policy/Support): Insurance coverage, government aid, legal changes, school support.
   - 생활/관리 (Life/Management): Diet, insulin pumps/CGM, daily management tips, mental health.
   - 사회/인식 (Society/Awareness): Awareness campaigns, discrimination issues, personal stories, events.
   - 기타 (Other): General or unrelated.

2. Type (Choose one):
   - 연구결과 (Research): Scientific findings, medical breakthroughs.
   - 정책발표 (Policy): Official government announcements, new laws or regulations.
   - 행사/캠페인 (Event): Walks, camps, donations, awareness events.
   - 개인사례 (Story): Interviews, experiences, personal achievements.
   - 정보/팁 (Info): Educational content, management advice.
   - 기타 (Other): Unclear.

[Output Format]
Return ONLY a JSON object. Do not include markdown formatting (```json ... ```).
{{
  "category": "...",
  "type": "..."
}}
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            print(f"LLM Classification Error: {e}")
            return None

    def check_similarity(self, new_title, existing_summaries):
        """
        Checks if the new article is semantically similar to any of the existing articles.
        existing_summaries: list of strings (e.g., "Title: ...")
        Returns: (True, "Similar Title") or (False, None)
        """
        if not self.client or not existing_summaries:
            return False, None
            
        # Check only against the last 20 articles to save tokens and time
        recent_summaries = existing_summaries[-20:]
        
        prompt = f"""
Determine if the [New Article] is effectively covering the SAME EVENT or TOPIC as any of the [Existing Articles].
Ignore minor differences in phrasing. Focus on the core event/subject.

[New Article]
{new_title}

[Existing Articles]
{chr(10).join(recent_summaries)}

[Task]
If the [New Article] is a duplicate of any existing one, return the Title of the existing article.
If it is new, return "NEW".

Return ONLY the result string.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            result = response.text.strip()
            if result == "NEW":
                return False, None
            else:
                return True, result
        except Exception as e:
            print(f"LLM Similarity Check Error: {e}")
            return False, None
