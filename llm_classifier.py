
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
Note: Type 1 Diabetes is officially recognized as a "Pancreatic Disability" (췌장장애) in Korea. Articles discussing "Pancreatic Disability" policy or issues are HIGHLY RELEVANT.
Analyze the following news article.

[Article]
Title: {title}
Content Snippet: {content[:1500]}

[Task 1: Classification]
Choose ONE category that best fits the article.
1. **정책/지원 (Policy)**: Insurance, government aid, laws, politics.
2. **의학/연구 (Medical)**: New drugs, treatments, clinical trials, medical studies.
3. **사회/환우 (Society)**: Awareness campaigns, donations, **Personal Stories** (Real patients only), events.
4. **경제/산업 (Economy)**: Pharma business, stock market, new product launches.
5. **생활/정보 (Life)**: Diet, devices (CGM, pumps), daily management tips.

*Note: If the article fits multiple, choose the most dominant one.*

**Irrelevant Definition**:
- Movie/Drama promotions (e.g., 'Sugar', Choi Ji-woo) -> IRRELEVANT.
- Passing mentions of diabetes in unrelated tops -> IRRELEVANT.
- If it is Irrelevant, set category to "관련없음".

[Task 2: Summarization]
- Summarize the **core message** of the article in 1-2 Korean sentences.
- Rewrite it as if explaining the key takeaway to a patient.
- Focus on "What is new?" or "What should I know?".

[Output Format]
Return ONLY a JSON object. Do not include markdown formatting (```json ... ```).
{{
  "category": "...",
  "summary": "..."
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
Determine if the [New Article] is effectively covering the **EXACT SAME SPECIFIC EVENT or PRESS RELEASE** as any of the [Existing Articles].

Rules:
1. Different articles about the same *general topic* (e.g., "Diabetes management tips") are **NOT** duplicates.
2. Different perspectives or interviews on the same issue are **NOT** duplicates.
3. Only mark as duplicate if they cover the **same specific event, announcement, or accident** on the same day.

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
