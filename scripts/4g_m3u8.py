import cloudscraper
import base64
import uuid
import datetime
import hashlib
import time
import json
import sys
import re
import warnings
import os
from urllib.parse import urljoin, urlparse, parse_qs, quote
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import requests
import logging

# 關閉所有警告和日誌
warnings.filterwarnings("ignore")

# 配置日誌
logging.basicConfig(level=logging.ERROR)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
log.disabled = True

# 默認配置
DEFAULT_USER_AGENT = "%E5%9B%9B%E5%AD%A3%E7%B7%9A%E4%B8%8A/4 CFNetwork/3826.500.131 Darwin/24.5.0"
DEFAULT_TIMEOUT = 30  # 增加超時時間
CHANNEL_DELAY = 3  # 增加頻道之間的延遲時間（秒）
MAX_RETRIES = 3  # 最大重試次數

# 默認賬號(可被環境變量覆蓋)
DEFAULT_USER = os.environ.get('GTV_USER', '')
DEFAULT_PASS = os.environ.get('GTV_PASS', '')

# 記憶體緩存
cache_play_urls = {}
CACHE_EXPIRATION_TIME = 86400  # 24小時有效期

def generate_uuid(user):
    """根據賬號和目前日期生成唯一 UUID，確保不同用戶每天 UUID 不同"""
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    name = f"{user}-{today}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name)).upper()

def generate_4gtv_auth():
    head_key = "PyPJU25iI2IQCMWq7kblwh9sGCypqsxMp4sKjJo95SK43h08ff+j1nbWliTySSB+N67BnXrYv9DfwK+ue5wWkg=="
    KEY = b"ilyB29ZdruuQjC45JhBBR7o2Z8WJ26Vg"
    IV = b"JUMxvVMmszqUTeKn"
    decoded = base64.b64decode(head_key)
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    decrypted = cipher.decrypt(decoded)
    pad_len = decrypted[-1]
    decrypted = decrypted[:-pad_len].decode('utf-8')
    today = datetime.datetime.utcnow().strftime('%Y%m%d')
    sha512 = hashlib.sha512((today + decrypted).encode()).digest()
    return base64.b64encode(sha512).decode()

def sign_in_4gtv(user, password, fsenc_key, auth_val, ua, timeout):
    url = "https://api2.4gtv.tv/AppAccount/SignIn"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "fsenc_key": fsenc_key,
        "fsdevice": "iOS",
        "fsversion": "3.2.8",
        "4gtv_auth": auth_val,
        "User-Agent": ua
    }
    payload = {"fsUSER": user, "fsPASSWORD": password, "fsENC_KEY": fsenc_key}
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({"User-Agent": ua})
    resp = scraper.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("Data") if data.get("Success") else None

def get_all_channels(ua, timeout):
    url = 'https://api2.4gtv.tv/Channel/GetChannelBySetId/1/pc/L/V'
    headers = {"accept": "*/*", "origin": "https://www.4gtv.tv", "referer": "https://www.4gtv.tv/", "User-AAgent": ua}
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({"User-Agent": ua})
    resp = scraper.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if data.get("Success"):
        return data.get("Data", [])
    return []

def get_4gtv_channel_url_with_retry(channel_id, fnCHANNEL_ID, fsVALUE, fsenc_key, auth_val, ua, timeout, max_retries=MAX_RETRIES):
    """帶重試機制的獲取頻道URL函數"""
    # 檢查緩存
    current_time = time.time()
    cache_key = f"{channel_id}_{fnCHANNEL_ID}"
    if cache_key in cache_play_urls:
        cache_time, url = cache_play_urls[cache_key]
        if current_time - cache_time < CACHE_EXPIRATION_TIME:
            return url
    
    for attempt in range(max_retries):
        try:
            headers = {
                "content-type": "application/json; charset=utf-8",
                "fsenc_key": fsenc_key,
                "accept": "*/*",
                "fsdevice": "iOS",
                "fsvalue": "",
                "fsversion": "3.2.8",
                "4gtv_auth": auth_val,
                "Referer": "https://www.4gtv.tv/",
                "User-Agent": ua,
                'X-Forwarded-For': '49.159.74.105'
            }
            payload = {
                "fnCHANNEL_ID": fnCHANNEL_ID,
                "clsAPP_IDENTITY_VALIDATE_ARUS": {"fsVALUE": fsVALUE, "fsENC_KEY": fsenc_key},
                "fsASSET_ID": channel_id,
                "fsDEVICE_TYPE": "mobile"
            }
            scraper = cloudscraper.create_scraper()
            scraper.headers.update({"User-Agent": ua})
            resp = scraper.post('https://api2.4gtv.tv/App/GetChannelUrl2', headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get('Success') and 'flstURLs' in data.get('Data', {}):
                url = data['Data']['flstURLs'][1]
                # 更新緩存
                cache_play_urls[cache_key] = (current_time, url)
                return url
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ 獲取頻道 {channel_id} 失敗，正在重試 ({attempt + 1}/{max_retries})")
                time.sleep(2)  # 重試前等待2秒
            else:
                print(f"❌ 獲取頻道 {channel_id} 失敗，已達到最大重試次數")
                return None
    return None

def get_highest_bitrate_url(master_url):
    """嘗試獲取更高質量的URL"""
    # 嘗試將720p替換為1080p
    if 'index.m3u8' in master_url:
        return master_url.replace('index.m3u8', '1080.m3u8')
    
    # 如果沒有720p，則保持原樣
    return master_url

def generate_m3u_playlist(user, password, ua, timeout, output_dir="playlist", delay=CHANNEL_DELAY):
    """生成M3U播放清單"""
    try:
        # 創建輸出目錄
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成認證信息
        fsenc_key = generate_uuid(user)
        auth_val = generate_4gtv_auth()
        fsVALUE = sign_in_4gtv(user, password, fsenc_key, auth_val, ua, timeout)
        
        if not fsVALUE:
            print("❌ 登錄失敗")
            return False
            
        # 獲取所有頻道
        channels = get_all_channels(ua, timeout)
        
        # 創建M3U文件
        m3u_content = "#EXTM3U\n"
        successful_channels = 0
        failed_channels = 0
        failed_list = []
        
        for channel in channels:
            channel_id = channel.get("fs4GTV_ID", "")
            channel_name = channel.get("fsNAME", "")
            channel_type = channel.get("fsTYPE_NAME", "")
            channel_logo = channel.get("fsLOGO_MOBILE", "")
            fnCHANNEL_ID = channel.get("fnID", "")
            
            # 只處理4gtv-live頻道
            if not channel_id.startswith("4gtv-live"):
                continue
                
            # 添加延遲
            time.sleep(delay)
                
            # 獲取頻道URL（帶重試機制）
            try:
                stream_url = get_4gtv_channel_url_with_retry(channel_id, fnCHANNEL_ID, fsVALUE, fsenc_key, auth_val, ua, timeout)
                if not stream_url:
                    print(f"❌ 無法獲取頻道 {channel_name} 的URL")
                    failed_channels += 1
                    failed_list.append(channel_name)
                    continue
                    
                # 嘗試獲取更高質量的URL
                highest_url = get_highest_bitrate_url(stream_url)
                
                # 添加到M3U內容
                m3u_content += f'#EXTINF:-1 tvg-id="{channel_name}" tvg-name="{channel_name}" tvg-logo="{channel_logo}" group-title="{channel_type}",{channel_name}\n'
                m3u_content += f"{highest_url}\n"
                
                print(f"✅ 已添加頻道: {channel_name}")
                successful_channels += 1
                
            except Exception as e:
                print(f"❌ 處理頻道 {channel_name} 時出錯: {e}")
                failed_channels += 1
                failed_list.append(channel_name)
                continue
        
        # 寫入文件
        output_path = os.path.join(output_dir, "4gtv.m3u")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        
        print(f"\n📊 播放清單生成完成: {output_path}")
        print(f"✅ 成功處理: {successful_channels} 個頻道")
        print(f"❌ 失敗處理: {failed_channels} 個頻道")
        
        if failed_list:
            print("\n📋 失敗頻道列表:")
            for channel in failed_list:
                print(f"   - {channel}")
        
        return True
        
    except Exception as e:
        print(f"❌ 生成播放清單時出錯: {e}")
        return False

def main():
    """主函數，提供命令行界面"""
    import argparse
    
    parser = argparse.ArgumentParser(description='4GTV 流媒體獲取工具')
    parser.add_argument('--generate-playlist', action='store_true', help='生成M3U播放清單')
    parser.add_argument('--user', type=str, default=DEFAULT_USER, help='用戶名')
    parser.add_argument('--password', type=str, default=DEFAULT_PASS, help='密碼')
    parser.add_argument('--ua', type=str, default=DEFAULT_USER_AGENT, help='用戶代理')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help='超時時間(秒)')
    parser.add_argument('--output-dir', type=str, default="playlist", help='輸出目錄')
    parser.add_argument('--delay', type=float, default=CHANNEL_DELAY, help='頻道之間的延遲時間(秒)')
    parser.add_argument('--retries', type=int, default=MAX_RETRIES, help='最大重試次數')
    
    args = parser.parse_args()
    
    if args.generate_playlist:
        success = generate_m3u_playlist(args.user, args.password, args.ua, args.timeout, args.output_dir, args.delay)
        return 0 if success else 1
    else:
        parser.print_help()
        return 1

if __name__ == '__main__':
    sys.exit(main())
