from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# サービスアカウントキーのJSONファイル
SERVICE_ACCOUNT_FILE = "credentials.json"

# Google Drive APIのスコープ
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# 認証
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

# APIクライアントの作成
service = build("drive", "v3", credentials=creds)

def upload_file(file_path, folder_id=None):
    """Google Drive にファイルをアップロード"""
    file_metadata = {"name": file_path.split("/")[-1]}
    
    if folder_id:
        file_metadata["parents"] = [folder_id]
    
    media = MediaFileUpload(file_path, mimetype="image/jpeg")  # 画像のMIMEタイプ変更可
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    
    print(f"アップロード完了: {file_path} (ID: {file.get('id')})")
    return file.get("id")

# アップロードする画像のパス
image_path = "sample.jpg"
upload_file(image_path)

FOLDER_ID = "1phhYUnErPNVnzY8JSG6pmidy70PU8fOy"
upload_file(image_path, folder_id=FOLDER_ID)
