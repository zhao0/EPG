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
DEFAULT_TIMEOUT = 10  # seconds
CACHE_FILE = os.path.expanduser('~/.4gtvcache.txt')
CACHE_TTL = 1 * 3600  # 2小時有效期

# 默認賬號(可被環境變量覆蓋)
DEFAULT_USER = os.environ.get('GTV_USER', '')
DEFAULT_PASS = os.environ.get('GTV_PASS', '')

# 加載緩存
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            CACHE = {k: (float(v[0]), v[1]) for k, v in raw.items()}
    except Exception:
        CACHE = {}
else:
    CACHE = {}

def save_cache():
    try:
        serializable = {k: [v[0], v[1]] for k, v in CACHE.items()}
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(serializable, f)
    except Exception as e:
        print(f"⚠️緩存儲存失敗: {e}")

def get_channel_info(fn_channel_id, ua, timeout):
    """獲取頻道信息"""
    get_channel_api = f'https://api2.4gtv.tv/Channel/GetChannel/{fn_channel_id}'
    headers = {
        'User-Agent': ua,
        'X-Forwarded-For': 'https://api2.4gtv.tv'
    }
    
    scraper = cloudscraper.create_scraper()
    scraper.headers.update(headers)
    response = scraper.get(get_channel_api, timeout=timeout)
    
    if response.status_code != 200:
        return None
        
    data = response.json()
    return data.get('Data', {})

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

def get_4gtv_channel_url(channel_id, fnCHANNEL_ID, fsVALUE, fsenc_key, auth_val, ua, timeout):
    headers = {
        "content-type": "application/json",
        "fsenc_key": fsenc_key,
        "accept": "*/*",
        "fsdevice": "iOS",
        "fsvalue": "",
        "fsversion": "3.2.8",
        "4gtv_auth": auth_val,
        "Referer": "https://www.4gtv.tv/",
        "User-Agent": ua
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
        return data['Data']['flstURLs'][1]
    return None

def get_highest_bitrate_url(master_url, fnCHANNEL_ID, ua, timeout):
    """獲取最高碼率的URL"""
    # 從API獲取頻道信息
    channel_info = get_channel_info(fnCHANNEL_ID, ua, timeout)
    if channel_info and 'lstALL_BITRATE' in channel_info:
        bitrates = channel_info['lstALL_BITRATE']
        if bitrates:
            # 找到最高碼率
            highest_bitrate = max([int(b) for b in bitrates if b.isdigit()])
            
            # 直接替換URL中的index.m3u8為最高碼率
            return master_url.replace('index.m3u8', f'{highest_bitrate}.m3u8')
    
    # 如果無法從API獲取，則返回原始URL
    return master_url

def generate_m3u_playlist(user, password, ua, timeout, output_dir="playlist"):
    """生成M3U播放清單"""
    try:
        # 創建輸出目錄
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成認證信息
        fsenc_key = generate_uuid(user)
        auth_val = generate_4gtv_auth()
        fsVALUE = sign_in_4gtv(user, password, fsenc_key, auth_val, ua, timeout)
        
        if not fsVALUE:
            print("登錄失敗")
            return False
            
        # 獲取所有頻道
        channels = get_all_channels(ua, timeout)
        
        # 創建M3U文件
        m3u_content = "#EXTM3U\n"
        
        for channel in channels:
            channel_id = channel.get("fs4GTV_ID", "")
            channel_name = channel.get("fsNAME", "")
            channel_type = channel.get("fsTYPE_NAME", "")
            channel_logo = channel.get("fsLOGO_MOBILE", "")
            fnCHANNEL_ID = channel.get("fnID", "")
            
            # 只處理4gtv-live頻道
            if not channel_id.startswith("4gtv-live"):
                continue
                
            # 獲取頻道URL
            stream_url = get_4gtv_channel_url(channel_id, fnCHANNEL_ID, fsVALUE, fsenc_key, auth_val, ua, timeout)
            if not stream_url:
                print(f"無法獲取頻道 {channel_name} 的URL")
                continue
                
            # 獲取最高碼率URL
            highest_url = get_highest_bitrate_url(stream_url, fnCHANNEL_ID, ua, timeout)
            
            # 添加到M3U內容
            m3u_content += f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{channel_name}" tvg-logo="{channel_logo}" group-title="{channel_type}",{channel_name}\n'
            m3u_content += f"{highest_url}\n"
            
            print(f"已添加頻道: {channel_name}")
        
        # 寫入文件
        output_path = os.path.join(output_dir, "4gtv.m3u")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        
        print(f"播放清單已生成: {output_path}")
        return True
        
    except Exception as e:
        print(f"生成播放清單時出錯: {e}")
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
    
    args = parser.parse_args()
    
    if args.generate_playlist:
        success = generate_m3u_playlist(args.user, args.password, args.ua, args.timeout, args.output_dir)
        return 0 if success else 1
    else:
        parser.print_help()
        return 1

if __name__ == '__main__':
    sys.exit(main())
