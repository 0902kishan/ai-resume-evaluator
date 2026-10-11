import json
import os
from pathlib import Path
from docx import Document
from dotenv import load_dotenv
from groq import Groq
from pypdf import PdfReader

load_dotenv()

my_api_key = os.getenv("GROQ_API_KEY")
if not my_api_key:
    raise ValueError("API key kaha hai bhai")

client = Groq(api_key=my_api_key)
model = "openai/gpt-oss-20b"  # remove duplicate `model =`

def read_pdf(file_path):
    reader = PdfReader(file_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def read_docx(file_path):
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

def read_resume(file_path):
    if file_path.suffix.lower() == ".pdf":
        return read_pdf(file_path)
    elif file_path.suffix.lower() == ".docx":
        return read_docx(file_path)
    return None

# This lets you hand it any file path, pdf or docx, and it figures out how to read it.'''
# read_resume(file_path) → checks extension → sends file_path ->
# → read_pdf() or read_docx() → extracts text → returns text.
job_description = Path("job_description.txt").read_text(encoding="utf-8")

from pydantic import BaseModel, Field

class ResumeEvaluation(BaseModel):
    score: int = Field(ge=0, le=100, description="Score from 0 to 100")
    strengths: str
    weaknesses: str
    suggestion: str

class ParsedResume(BaseModel):
    name: str | None = None
    email: str | None = None
    skills: list[str] = []
    experience_years: float | None = None
    education: list[str] = []

schema = ResumeEvaluation.model_json_schema()
how_response_come = {
    "type": "json_schema",
    "json_schema": {"name": "resume_evaluation", "schema": schema}
}

def parse_resume(resume_text):
    schema=ParsedResume.model_json_schema()
    system_prompt = f"""Extract the structured information from the resume. Return
    only valid JSON matching this schema: {schema}
if value is not present, return null or empty list. Do not include any extra text or explanation."""

    messages = [

        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role" : "user",
            "content": f"Resume:\n{resume_text}"
        }
    ]
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0,
        response_format={"type": "json_object"},  )
    import json
    data = json.loads(response.choices[0].message.content)
    return ParsedResume(**data)

system_prompt = """Compare the resume against this job description.
Give a score from 0 to 100 using this rubric:
- Skills match: 40 points
- Relevant experience: 35 points
- Education/projects: 15 points
- Resume clarity: 10 points

Return score, strengths, weaknesses, and suggestion."""

def score_resume(parsed_resume, job_description):
    prompt = f"""Resume (structured):
    {parsed_resume.model_dump_json(indent=2)}
     jon description:
     {job_description}"""
    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0,
        response_format=how_response_come,)
    data = json.loads(response.choices[0].message.content)
    return ResumeEvaluation(**data)
    
        

# 

resume_folder = Path("resumes")
all_results = []

for file in resume_folder.iterdir():
    if file.suffix.lower() not in [".pdf", ".docx"]:
        continue
    print(f"Processing {file.name}...")

    resume_text = read_resume(file)
    parsed = parse_resume(resume_text)
    result = score_resume(parsed, job_description)

    all_results.append({
        "name": parsed.name or file.name,
        "score": result.score,
        "strengths": result.strengths,
        "weaknesses": result.weaknesses,
    })

sorted_results = sorted(all_results, key=lambda x: x["score"], reverse=True)

print("\nTOP 2")
for c in sorted_results[:2]:
    print(c["name"], "-", c["score"])

print("\nLOWEST 2")
for c in sorted_results[-2:]:
    print(c["name"], "-", c["score"])

