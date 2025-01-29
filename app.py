# 画像処理
import io
import cv2
from PIL import Image
import numpy as np
#import pickle

# env, flask
import os
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

from io import BytesIO
import random

load_dotenv()

CHANNEL_ACCESS_TOKEN=os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET=os.environ.get("CHANNEL_SECRET")

app = Flask(__name__)

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

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


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='シールの写真をおくってね♪'))
        #TextSendMessage(text=event.message.text+'ってなに？'))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)

    result = count_stickers(message_content.content)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='今日もお疲れ様でした♪\n\n＜本日の結果＞\n'+result)
        )

def count_stickers(image):
    img_bn = io.BytesIO(image)
    img_pil = Image.open(img_bn)
    image = np.asarray(img_pil)
    image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
    
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

    result_str = ''
    for quadrant_name, counts in results.items():
        count_sum = 0
        for color, count in counts.items():
            count_sum += count
        result_str += f"{quadrant_name}: {count_sum}\n"
        result_str += f"{'●'*count_sum}\n"

    return result_str

if __name__ == "__main__":
    app.run()

