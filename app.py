# 画像処理
import io
import cv2
from PIL import Image
import numpy as np
from io import BytesIO

# env, flask
import os
import base64
from dotenv import load_dotenv
from flask import Flask, request, abort

# linebot
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageMessage, ImageSendMessage,
)

# 画像ファイル名出力用
import datetime
import random
import string

# Google Drive関連
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import gspread

# 環境変数の読み込み
load_dotenv()
CHANNEL_ACCESS_TOKEN=os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET=os.environ.get("CHANNEL_SECRET")
GOOGLE_CREDENTIALS=os.environ.get("GOOGLE_CREDENTIALS")
FOLDER_ID=os.environ.get("FOLDER_ID")
SPREADSHEET_ID=os.environ.get("SPREADSHEET_ID")

# GOOGLE_CREDENTIALSからcredentials.jsonを作成
if GOOGLE_CREDENTIALS:
    with open("credentials.json", "wb") as f:
        f.write(base64.b64decode(GOOGLE_CREDENTIALS))

# Flask appの初期設定
app = Flask(__name__)

# Line BotのACCESS TOKENおよびSECRETのセット
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Flaskの動作確認用
@app.route("/")
def hello_world():
    return "hello world!"

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body ae text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# テキストメッセージが来た時の対応
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='シールの写真をおくってね♪'))
        #TextSendMessage(text=event.message.text+'ってなに？'))

# 画像が送られてきた時の対応
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id 
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)

    result = count_stickers(message_content.content, user_id)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='今日もお疲れ様でした♪\n集計結果はこちら！\n'+result)
        )

# 画像からシールの数をカウントする関数
def count_stickers(image, user_id):
    img_bn = io.BytesIO(image)
    img_pil = Image.open(img_bn)
    image = np.asarray(img_pil)
    image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)

    # GoogleDrive保存用のファイルを一時的に保存 
    now = datetime.datetime.now()
    now = now + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y%m%d_%H%M%S")
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    tmp_img_filename = './' + user_id + '_' + time_str + '_' + random_str + '.jpg'
    cv2.imwrite(tmp_img_filename, image)
    upload_file(tmp_img_filename, FOLDER_ID)
    os.remove(tmp_img_filename)
    
    # 画像サイズを取得
    height, width, _ = image.shape

    # 領域ごとに結果を保存する辞書
    results = {
        "おしゃべり": {},
        "ごはん": {},
        "べんきょう": {},
        "おあそび": {}
    }

    # 領域を4分割
    quadrants = {
        "おしゃべり": image[0:height//2, 0:width//2],
        "ごはん": image[0:height//2, width//2:width],
        "べんきょう": image[height//2:height, 0:width//2],
        "おあそび": image[height//2:height, width//2:width],
    }

    # 色範囲を設定 (HSV形式)
    color_ranges = {
        "赤": [(0, 100, 100), (10, 255, 255)],      # 赤色
        "緑": [(40, 50, 50), (80, 255, 255)],    # 緑色
        "青": [(100, 150, 50), (120, 255, 255)],  # 青色
        "黄": [(20, 100, 100), (30, 255, 255)], # 黄色
    }

    # 各領域を処理
    for quadrant_name, quadrant in quadrants.items():
        # BGR画像をHSVに変換
        hsv = cv2.cvtColor(quadrant, cv2.COLOR_BGR2HSV)

        # 各色ごとの丸をカウント
        circle_counts = {}
        for color, (lower, upper) in color_ranges.items():
            lower = np.array(lower)
            upper = np.array(upper)

            # 色範囲のマスクを作成
            mask = cv2.inRange(hsv, lower, upper)

            # 輪郭を検出
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # 円の数をカウント
            circles = 0
            for contour in contours:
                (x, y), radius = cv2.minEnclosingCircle(contour)
                if radius > 5:  # 半径が小さすぎるものを除外
                    circles += 1

            circle_counts[color] = circles
        
        # 結果を保存
        results[quadrant_name] = circle_counts
    
    new_data = []
    datetime_str = now.strftime("%Y/%m/%d %H:%M:%S")
    for quadrant_name, circle_counts in results.items():
        for color, counts in circle_counts.items():
            new_data.append([datetime_str, user_id, quadrant_name, color, counts])
    
    add_to_gspread(new_data)

    result_str = ''
    for quadrant_name, counts in results.items():
        count_sum = 0
        for color, count in counts.items():
            count_sum += count
        result_str += f"\n{quadrant_name}: {count_sum}\n"
        result_str += f"{'●'*count_sum}\n"

    return result_str

def upload_file(file_path, folder_id=None):
    # サービスアカウントキーのJSONファイル
    SERVICE_ACCOUNT_FILE = "credentials.json"
    # Google Drive APIのスコープ
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    # GoogleDrive認証
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    # GoogleDriveAPIクライアントの作成
    service = build("drive", "v3", credentials=creds)

    """Google Drive にファイルをアップロード"""
    file_metadata = {"name": file_path.split("/")[-1]}
    
    if folder_id:
        file_metadata["parents"] = [folder_id]
    
    media = MediaFileUpload(file_path, mimetype="image/jpeg")  # 画像のMIMEタイプ変更可
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    
    return file.get("id")

def add_to_gspread(data):
    # サービスアカウントキーのJSONファイル
    SERVICE_ACCOUNT_FILE = "credentials.json"
    # Google Spreadsheet APIのスコープ
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    # GoogleDrive認証
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    # GoogleSpreadsheetAPIクライアントの作成
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1  # シート名を指定
    sheet.append_rows(data)

# Flask app の起動
if __name__ == "__main__":
    app.run()

