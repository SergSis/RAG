from flask import Flask, request, jsonify, url_for
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from typing import Any, List, Tuple
from pinecone import Pinecone
import json
import pandas as pd
import requests
import re
import urllib.parse
import numpy as np
import logging

id_operator = {
}

load_dotenv()

class Settings(BaseSettings):
    API_KEY_PINECONE: SecretStr
    OPENAI_API_KEY: SecretStr
    API_OMNIDESK: SecretStr
    EMAIL: str

    class Config:
        env_file = ".env"

settings = Settings()

pc = Pinecone(api_key=settings.API_KEY_PINECONE.get_secret_value())
index = pc.Index("iridi")

model = SentenceTransformer('intfloat/multilingual-e5-large')

app = Flask(__name__)

OPENAI_URL = 'https://api.openai.com/v1/chat/completions'

EMAIL = settings.EMAIL
API_OMNIDESK = settings.API_OMNIDESK.get_secret_value()

headers_gpt = {
  'Content-Type': 'application/json',
  'Authorization': 'Bearer'
}

headers_omni = {
  'Content-Type': 'application/json',
}

def clean_html_and_truncate_text(html_text: str) -> str:
  try:
    clean_text = BeautifulSoup(html_text, 'html.parser').get_text()

    clean_text = re.sub(r'\n+', ' ', clean_text)

    truncated_text = re.split(r'--*?С уважением', clean_text, flags=re.DOTALL)[0]
    truncated_text = re.split(r'--', truncated_text, flags=re.DOTALL)[0]
    truncated_text = re.split(r'С уважением', truncated_text, flags=re.DOTALL)[0]

    return truncated_text.strip()

  except Exception as e:
    print(f"Error in clean_html_and_truncate_text: {e}")
    return None

def сlear_html(text: str) -> str:
  message_user = []

  try:
    soup = BeautifulSoup(text, "html.parser")
    div_tag = soup.find('div', {'class': 'omni_orig_reply'})
    div_tag.decompose()
    message_user.append(str(soup.get_text()))
  except AttributeError:
    soup = BeautifulSoup(text, "html.parser")
    message_user.append(soup.get_text())
  except TypeError as e:
    message_user.append(None)
    print(f"Error in TypeError: {e}")
    return message_user


def getAllMessagesFromOmnideskTicketAndSendToFAQ(json_response: Any) -> Tuple[List[str], List[str]]:
  message_oper = []
  message_user = []

  try:
    for i in range(len(json_response)):
      message = json_response.get(str(i), {}).get("message", {})
      user_id = message.get("user_id", None)
      content = message.get("content", '')
      content_html = message.get("content_html", '')
      sent_via_rule = message.get("sent_via_rule", False)
      note = message.get("note", False)
      is_viewed = message.get("is_viewed", False)

      if user_id != 0:
        if content:
          text_user = clean_html_and_truncate_text(content)
          message_user.append(f"Сообщение пользователя: {text_user}")
          message_oper.append(None)
        elif content_html:
          text_user = clean_html_and_truncate_text(content_html)
          message_user.append(f"Сообщение пользователя: {text_user}")
          message_oper.append(None)
      else:
        if content and not sent_via_rule and not note and is_viewed:
          text_oper = clean_html_and_truncate_text(content)
          message_oper.append(f"Сообщение технической поддержки: {text_oper}")
          message_user.append(None)
        elif content_html and not sent_via_rule and not note and is_viewed:
          text_oper = clean_html_and_truncate_text(content_html)
          message_oper.append(f"Сообщение технической поддержки: {text_oper}")
          message_user.append(None)

    return message_oper, message_user
  except Exception as e:
    print(f'Error in getAllMessagesFromOmnideskTicketAndSendToFAQ: {e}')


def separation_messages_gpt(message_gpt: str, question_text: str ='** Вопрос **', answer_text: str ='** Ответ **') -> Tuple[str, str]:
  if message_gpt.find(question_text) == -1 and message_gpt.find(answer_text) == -1:

    question_start = message_gpt.find(question_text) + len(question_text)
    answer_start = message_gpt.find(answer_text)

  question = message_gpt[question_start:answer_start].strip()
  answer = message_gpt[answer_start + len(answer_text):].strip()
  return question, answer

def call_openai(messages: str, max_tokens: int) -> str:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {settings.OPENAI_API_KEY.get_secret_value()}'
    }
    payload = {
        'model': 'gpt-4o-mini-2024-07-18',
        'messages': messages,
        'max_tokens': max_tokens
    }
    resp = requests.post(OPENAI_URL, headers=headers, json=payload)
    resp.raise_for_status()
    result = resp.json()
    return result['choices'][0]['message']['content']

def get_tikets_message(case_number: str) -> Dict[str]:
  try:
    response = requests.get(
      f'https://iridi.omnidesk.ru/api/cases/{case_number}/messages.json',
      headers=headers_omni,
      auth=(f'{EMAIL}@iridiummobile.ru', f'{API_OMNIDESK}'),
    )
    json_response = json.loads(response.text)
    return json_response
  except Exception as e:
    print(f"Error in get_tikets_message: {e}")


@app.route('/clear_text_create_embedd/', methods=['POST'])
def clear_text_create_embedd():
  try:
    encoded_text = request.data
    decoded_text = encoded_text.decode('utf-8')

    params = urllib.parse.parse_qs(decoded_text)

    data = {key: urllib.parse.unquote(value[0]) for key, value in params.items()}

    print(f"utf-8: {data}")

    df_data = pd.DataFrame(data, index=[0])
    print(df_data)

    if "function_name" not in df_data:
      if "case_subject" in df_data:
        case_subject = df_data["case_subject"].iloc[0]

      elif "case_description" in df_data:
        case_subject = df_data["case_description"].iloc[0]

      else:
        case_subject = df_data["last_message"].iloc[0]

      case_number = df_data["case_number"].iloc[0]
      try:
        staff_id = df_data["staff_id"].iloc[0]
        name_oper = id_operator[staff_id]
      except:
        name_oper = ""

      questuon = clean_html_and_truncate_text(case_subject)
      to_gpt = """
      Тебе представленная вопрос от клиента. Нужно сформировать один вопрос. Вопрос, обязательно должен быть сформирован на основе переписки.
        Правила которым ты должен следовать:
        1) Пиши только на русском языке
        2) Если вопрос содержит лицензии, даты, версии прошивок или устройств, Но нужно пропустить написание этой информации
        3) Старайся сделать вопрос кратким
      """

      new_questuon = call_openai(to_gpt, questuon)
      embedded = create_embedded(new_questuon)
      request_pinecone = post_pinecone(embedded)

      message_oper_1 = request_pinecone["matches"][0]["metadata"]["message_oper"]
      message_oper_2 = request_pinecone["matches"][1]["metadata"]["message_oper"]

      message_oper = {"message_oper_1": message_oper_1,
                      "message_oper_2": message_oper_2}
      score = {"score_1": request_pinecone["matches"][0]["score"],
               "score_2": request_pinecone["matches"][1]["score"]}
      tag = {"tag_1":request_pinecone["matches"][0]["metadata"]["tag"],
             "tag_2":request_pinecone["matches"][1]["metadata"]["tag"]}
      id = {"id_1":request_pinecone["matches"][0]["id"],
            "id_2":request_pinecone["matches"][1]["id"]}

      to_gpt = """
      Тебе представленная ответ от технической поддержки.
      Сделай на основе этих 2 ответов, новый, но сформированных на основе предыдущих двух, с учетом их контекста.
      """

      message_gpt = call_openai(to_gpt, f"Ответ №1: {message_oper_1}, Ответ №2 {message_oper_2}")

      fitback_data = {"case_subject":new_questuon,
                      "case_number":case_number,
                      "name_oper":name_oper,
                      "message_gpt":message_gpt,
                      "message_oper":message_oper,
                      "score":score,
                      "tag":tag,
                      "id":id}
      print(fitback_data)
      fitback_json = json.dumps(fitback_data)
      return jsonify(fitback_json)
  except Exception as e:
    print(f"Error in clear_text_create_embedd: {e}")

@app.route('/create_embedded/', methods=['POST'])
def post_create_embedded():
  try:
    data = request.get_json()
    data = json.loads(data)
    df_data = pd.DataFrame([data])

    case_subject = df_data["case_subject"]
    case_number = df_data["case_number"]

    embedd = create_embedded(case_subject)

    answer_pinecone = post_pinecone(embedd)

    fitback_data = {"answer_pinecone":answer_pinecone, "case_number":case_number, "case_subject":case_subject}
    fitback_data = json(fitback_data)

    return jsonify(fitback_data)
  except Exception as e:
    print(f"Error in post_create_embedded: {e}")

@app.route("/saving_omnidesk_summary/", methods=['POST'])
def post_saving_omnidesk_summary():
  try:
    data = request.get_json()
    data = json.loads(data)
    df_data = pd.DataFrame(data)

    question = df_data["message_user"]
    answer = df_data["message_oper"]
    case_number = df_data["url_tiket"]
    tag = df_data["tag"]
    id = df_data["id"]

    clean_question = clean_html_and_truncate_text(question)
    embedd_message = model.encode(clean_question)

    data_pinecone = index.query(
      vector=embedd_message.tolist(),
      top_k=1,
      include_values=False,
      include_metadata=False,
    )
    if data_pinecone["matches"][0]["score"] < 0.95:
      index.upsert(
        vectors=[
          {
            "id": f"{id}",
            "values": embedd_message.tolist(),
            "metadata": {"message_user": question,
                         "clean_text_user": clean_question,
                         "message_oper": answer,
                         "url_tiket": case_number,
                         "tag":tag}
          }
        ]
      )

  except Exception as e:
    print(f"Error in post_saving_omnidesk_summary: {e}")


@app.route('/create_embedded_telegram/', methods=['POST'])
def post_create_embedded_telegram():
  try:
    data = request.get_json()
    print(data)

    embedded = create_embedded(data["question_user"])

    answer_pinecone = post_pinecone(embedded)

    ansewer_1 = answer_pinecone["matches"][0]["metadata"]["message_oper"]
    ansewer_2 = answer_pinecone["matches"][1]["metadata"]["message_oper"]

    fitback_data = {"ansewer_1":ansewer_1, "ansewer_2":ansewer_2}

    return jsonify(fitback_data)
  except Exception as e:
    print(f"Error in post_create_embedded: {e}")

@app.route("/clear_data_omni_tikets/", methods=['POST'])
def post_clear_data_omni_tikets():
  try:
    encoded_text = request.data
    decoded_text = encoded_text.decode('utf-8')

    params = urllib.parse.parse_qs(decoded_text)

    data = {key: urllib.parse.unquote(value[0]) for key, value in params.items()}
    print(f"utf-8: {data}")

    df_data = pd.DataFrame(data, index=[0])
    print(data)

    case_number = data["case_number"]
    promt = data["system_gpt"]
    json_response = get_tikets_message(case_number)
    print(f"json_response: {json_response}")

    message_oper, message_user = getAllMessagesFromOmnideskTicketAndSendToFAQ(json_response)
    print(message_oper, message_user)

    to_gpt = [text for message in zip(message_oper, message_user) for text in message]
    print(f"to_gpt: {to_gpt}")

    message_gpt = call_openai(to_gpt, promt)
    question, answer = separation_messages_gpt(message_gpt)
    fitback_data = {"to_gpt":to_gpt, "message_gpt": message_gpt, "question": question, "answer": answer, "case_number": f"https://iridi.omnidesk.ru/staff/cases/record/{case_number}"}

    return jsonify(fitback_data)
  except Exception as e:
    print(f"Error in post_clear_data_omni_tikets:  {e}")
@app.route('/relevance_answer_gpt/', methods=["GET"])
def post_relevance_answer_gpt():
  try:
    print(request)
    full_url = request.json
    print(f"post_relevance_answer_gpt: {full_url}")
  except Exception as e:
    print(f"Error in post_relevance_answer_gpt: {e}")

@app.route('/rateGPT', methods=['GET'])
def rate_case():
  case_number = request.args.get("case_number")
  rate = request.args.get("rate")

  try:
    case_data = {
      "function_name": "rateGPT",
      "case_number": case_number,
      "rate": rate
    }
    url = "https://script.google.com/macros/s/---/exec"

    respons = requests.post(url, json=case_data)
    print(respons)
    if respons.status_code == 200:
      print(f"Response JSON: {respons.json}")
    else:
      print(f"Error response: {respons.status_code}")
    return jsonify({
      "case_number": case_number,
      "rate": rate,
      "status": "Information recorded"
    })
  except Exception as e:
    print(f"Error in rateGPT: {e}")



@app.route('/', methods=['GET'])
def test_get():
  return "Все работает"


def create_embedded(data: List[str]) -> List[float]:
  embedded = model.encode(data, normalize_embeddings=True)
  return embedded.tolist()

def post_pinecone(embedded: List[float], top_k: int = 2) -> Dict[str, Any]:
  request_pinecone = index.query(
    vector=embedded,
    include_values=False,
    include_metadata=True,
  )

  return request_pinecone


if __name__ == "__main__":
    app.run(host="127.0.0.1", port="1212", threaded=True)
