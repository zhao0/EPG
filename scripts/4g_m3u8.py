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
import concurrent.futures
from threading import Lock

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
CHANNEL_DELAY = 1  # 增加頻道之間的延遲時間（秒）
MAX_RETRIES = 3  # 增加重試次數
DEFAULT_WORKERS = 5  # 默認併發工作線程數

# 默認賬號(可被環境變量覆蓋)
DEFAULT_USER = os.environ.get('GTV_USER', '')
DEFAULT_PASS = os.environ.get('GTV_PASS', '')

# 代理設置(可被環境變量覆蓋)
HTTP_PROXY = os.environ.get('http_proxy', '')
HTTPS_PROXY = os.environ.get('https_proxy', '')

# 記憶體緩存
cache_play_urls = {}
CACHE_EXPIRATION_TIME = 86400  # 24小時有效期

# 線程安全的鎖
cache_lock = Lock()
progress_lock = Lock()

def get_proxies():
    """從環境變量獲取代理設置"""
    proxies = {}
    if HTTP_PROXY:
        proxies['http'] = HTTP_PROXY
    if HTTPS_PROXY:
        proxies['https'] = HTTPS_PROXY
    return proxies if proxies else None

def create_scraper_with_proxy(ua):
    """創建帶有代理支持的scraper - 用於獲取播放地址"""
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({"User-Agent": ua})
    
    # 設置代理
    proxies = get_proxies()
    if proxies:
        scraper.proxies.update(proxies)
        print(f"🔌 使用代理: {proxies}")
    
    return scraper

def create_scraper_without_proxy(ua):
    """創建不帶代理的scraper - 用於登錄和獲取頻道列表"""
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({"User-Agent": ua})
    return scraper

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

def sign_in_4gtv(user, password, fsenc_key, auth_val, ua, timeout, max_retries=3):
    """登錄4GTV，帶重試機制 - 不使用代理"""
    url = "https://api2.4gtv.tv/AppAccount/SignIn"
    
    for attempt in range(max_retries):
        try:
            headers = {
                "Content-Type": "application/json; charset=UTF-8",
                "fsenc_key": fsenc_key,
                "fsdevice": "iOS",
                "fsversion": "3.2.8",
                "4gtv_auth": auth_val,
                "User-Agent": ua
            }
            payload = {"fsUSER": user, "fsPASSWORD": password, "fsENC_KEY": fsenc_key}
            
            print(f"🔑 嘗試登錄 (第 {attempt + 1} 次)...")
            # 使用不帶代理的scraper進行登錄
            scraper = create_scraper_without_proxy(ua)
            
            resp = scraper.post(url, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("Success"):
                print("✅ 登錄成功")
                return data.get("Data")
            else:
                error_msg = data.get('Message', '未知錯誤')
                print(f"❌ 登錄失敗: {error_msg}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"⏳ 等待 {wait_time} 秒後重試...")
                    time.sleep(wait_time)  # 指數退避
                    continue
                return None
                
        except Exception as e:
            print(f"❌ 登錄請求異常 (第 {attempt + 1} 次): {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"⏳ 等待 {wait_time} 秒後重試...")
                time.sleep(wait_time)  # 指數退避
                continue
            return None
    
    return None

def get_all_channels(ua, timeout):
    """獲取所有頻道集合的頻道，並去除重複頻道 - 不使用代理"""
    channel_sets = [1, 2, 33, 4]  # 已知的頻道集合ID
    all_channels = []
    seen_channel_ids = set()  # 用於跟踪已看到的頻道ID
    
    for set_id in channel_sets:
        print(f"📡 正在獲取頻道集合 {set_id}...")
        url = f'https://api2.4gtv.tv/Channel/GetChannelBySetId/{set_id}/pc/L/V'
        headers = {"accept": "*/*", "origin": "https://www.4gtv.tv", "referer": "https://www.4gtv.tv/", "User-AAgent": ua}
        # 使用不帶代理的scraper獲取頻道列表
        scraper = create_scraper_without_proxy(ua)
        
        try:
            resp = scraper.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("Success"):
                channels = data.get("Data", [])
                for channel in channels:
                    channel_id = channel.get("fs4GTV_ID", "")
                    # 檢查是否已經處理過這個頻道
                    if channel_id not in seen_channel_ids:
                        seen_channel_ids.add(channel_id)
                        all_channels.append(channel)
                        print(f"   ✅ 添加頻道: {channel.get('fsNAME', '未知')}")
                    else:
                        print(f"   ⏭️  跳過重複頻道: {channel.get('fsNAME', '未知')}")
            else:
                print(f"   ❌ 獲取頻道集合 {set_id} 失敗: {data.get('Message', '未知錯誤')}")
        except Exception as e:
            print(f"   ❌ 獲取頻道集合 {set_id} 失敗: {e}")
            continue
    
    return all_channels

def get_4gtv_channel_url_with_retry(channel_id, fnCHANNEL_ID, fsVALUE, fsenc_key, auth_val, ua, timeout, max_retries=MAX_RETRIES):
    """帶重試機制的獲取頻道URL函數 - 使用代理"""
    # 檢查緩存
    current_time = time.time()
    cache_key = f"{channel_id}_{fnCHANNEL_ID}"
    
    with cache_lock:
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
                "User-Agent": ua
            }
            payload = {
                "fnCHANNEL_ID": fnCHANNEL_ID,
                "clsAPP_IDENTITY_VALIDATE_ARUS": {"fsVALUE": fsVALUE, "fsENC_KEY": fsenc_key},
                "fsASSET_ID": channel_id,
                "fsDEVICE_TYPE": "mobile"
            }
            # 使用帶代理的scraper獲取播放地址
            scraper = create_scraper_with_proxy(ua)
            
            resp = scraper.post('https://api2.4gtv.tv/App/GetChannelUrl2', headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get('Success') and 'flstURLs' in data.get('Data', {}):
                url = data['Data']['flstURLs'][1]
                # 更新緩存
                with cache_lock:
                    cache_play_urls[cache_key] = (current_time, url)
                return url
            else:
                print(f"   ❌ 獲取頻道URL失敗: {data.get('Message', '未知錯誤')}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指數退避
                    continue
            return None
        except Exception as e:
            print(f"   ❌ 獲取頻道URL異常: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指數退避
                continue
            else:
                return None
    return None

def get_highest_bitrate_url(master_url):
    """嘗試獲取更高質量的URL - 只對特定開頭的網址進行處理"""
    # 只對以 "https://4gtvfree-mozai.4gtv.tv" 開頭的網址進行處理
    if master_url.startswith("https://4gtvfree-mozai.4gtv.tv") and 'index.m3u8' in master_url:
        return master_url.replace('index.m3u8', '1080.m3u8')
    
    # 對於其他網址，保持原樣
    return master_url

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█', print_end="\r"):
    """
    打印進度條
    @params:
        iteration   - 目前進度 (Int)
        total       - 總數 (Int)
        prefix      - 前綴字符串 (Str)
        suffix      - 後綴字符串 (Str)
        decimals    - 小數位數 (Int)
        length      - 進度條長度 (Int)
        fill        - 進度條填充字符 (Str)
        print_end   - 結束字符 (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
    # 如果完成，打印新行
    if iteration == total: 
        print()

def process_single_channel(channel_data, fsVALUE, fsenc_key, auth_val, ua, timeout, index, total_channels):
    """處理單個頻道的函數，用於併發執行"""
    channel_id = channel_data.get("fs4GTV_ID", "")
    channel_name = channel_data.get("fsNAME", "")
    channel_type = channel_data.get("fsTYPE_NAME", "其他")
    channel_logo = channel_data.get("fsLOGO_MOBILE", "")
    fnCHANNEL_ID = channel_data.get("fnID", "")
    
    # 處理頻道類型
    if channel_type:
        channel_type = channel_type.split(',')[0]
    
    # 檢查是否為fast-live開頭，如果是則修改類型為FastTV飛速看
    if channel_id.startswith('fast-live'):
        channel_type = "FastTV飛速看"
    
    # 獲取頻道URL（帶重試機制）
    try:
        stream_url = get_4gtv_channel_url_with_retry(channel_id, fnCHANNEL_ID, fsVALUE, fsenc_key, auth_val, ua, timeout)
        if not stream_url:
            return {
                "success": False,
                "channel_name": channel_name,
                "error": "無法獲取URL",
                "index": index
            }
            
        # 嘗試獲取更高質量的URL（僅對特定域名）
        highest_url = get_highest_bitrate_url(stream_url)
        
        # 構建M3U條目
        m3u_entry = f'#EXTINF:-1 tvg-id="{channel_name}" tvg-name="{channel_name}" tvg-logo="{channel_logo}" group-title="{channel_type}",{channel_name}\n'
        m3u_entry += f"{highest_url}\n"
        
        # 更新進度條
        with progress_lock:
            print_progress_bar(index + 1, total_channels, prefix='進度:', suffix=f'完成 {index+1}/{total_channels}')
        
        return {
            "success": True,
            "channel_name": channel_name,
            "m3u_entry": m3u_entry,
            "index": index
        }
        
    except Exception as e:
        return {
            "success": False,
            "channel_name": channel_name,
            "error": str(e),
            "index": index
        }

def generate_m3u_playlist(user, password, ua, timeout, output_dir="playlist", delay=CHANNEL_DELAY, workers=DEFAULT_WORKERS):
    """生成M3U播放清單 - 使用併發處理"""
    try:
        # 建立輸出目錄
        os.makedirs(output_dir, exist_ok=True)
        
        # 檢查賬號密碼
        if not user or not password:
            print("❌ 錯誤: 未提供賬號或密碼")
            print("💡 請通過環境變量 GTV_USER 和 GTV_PASS 設置，或使用 --user 和 --password 參數")
            return False
        
        print("🔑 正在生成認證信息...")
        # 生成認證信息
        fsenc_key = generate_uuid(user)
        auth_val = generate_4gtv_auth()
        
        print(f"📝 生成的 UUID: {fsenc_key}")
        print(f"🔐 生成的認證: {auth_val}")
        
        # 顯示代理信息
        proxies = get_proxies()
        if proxies:
            print(f"🔌 播放地址獲取將使用代理: {proxies}")
        else:
            print("🔌 播放地址獲取不使用代理")
        
        fsVALUE = sign_in_4gtv(user, password, fsenc_key, auth_val, ua, timeout, max_retries=3)
        
        if not fsVALUE:
            print("❌ 登錄失敗，請檢查:")
            print("   - 賬號密碼是否正確")
            print("   - 網絡連接是否正常")
            return False
        
        print("📡 正在獲取頻道清單...")
        # 獲取所有頻道
        channels = get_all_channels(ua, timeout)
        
        if not channels:
            print("❌ 無法獲取頻道清單")
            return False
            
        print(f"📺 共找到 {len(channels)} 個頻道")
        print(f"🚀 開始使用 {workers} 個工作線程併發處理頻道...")
        
        # 建立M3U檔案
        m3u_content = "#EXTM3U\n"
        successful_channels = 0
        failed_channels = 0
        failed_list = []
        
        # 使用線程池併發處理頻道
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有任務
            future_to_channel = {
                executor.submit(
                    process_single_channel, 
                    channel, 
                    fsVALUE, 
                    fsenc_key, 
                    auth_val, 
                    ua, 
                    timeout, 
                    index, 
                    len(channels)
                ): (index, channel.get("fsNAME", ""))
                for index, channel in enumerate(channels)
            }
            
            # 收集結果
            results = []
            for future in concurrent.futures.as_completed(future_to_channel):
                index, channel_name = future_to_channel[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    print(f'\n❌ 頻道 {channel_name} 產生異常: {exc}')
                    results.append({
                        "success": False,
                        "channel_name": channel_name,
                        "error": str(exc),
                        "index": index
                    })
        
        # 按原始順序排序結果
        results.sort(key=lambda x: x["index"])
        
        # 處理結果
        for result in results:
            if result["success"]:
                m3u_content += result["m3u_entry"]
                successful_channels += 1
            else:
                failed_channels += 1
                failed_list.append((result["channel_name"], result["error"]))
        
        # 寫入檔案
        output_path = os.path.join(output_dir, "4gtv.m3u")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        
        print(f"\n🎉 播放清單生成完成: {output_path}")
        print(f"✅ 成功處理: {successful_channels} 個頻道")
        print(f"❌ 失敗處理: {failed_channels} 個頻道")
        print(f"⚡ 使用 {workers} 個併發工作線程，處理時間大幅降低")
        
        if failed_list:
            print("\n📋 失敗頻道清單:")
            for channel_name, error in failed_list:
                print(f"   - {channel_name}: {error}")
        
        return True
        
    except Exception as e:
        print(f"❌ 生成播放清單時出錯: {e}")
        import traceback
        traceback.print_exc()
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
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS, help=f'併發工作線程數 (默認: {DEFAULT_WORKERS})')
    parser.add_argument('--verbose', action='store_true', help='顯示詳細處理信息')
    parser.add_argument('--http-proxy', type=str, help='HTTP代理服務器')
    parser.add_argument('--https-proxy', type=str, help='HTTPS代理服務器')
    
    args = parser.parse_args()
    
    # 設置代理（命令行參數優先於環境變量）
    global HTTP_PROXY, HTTPS_PROXY
    if args.http_proxy:
        HTTP_PROXY = args.http_proxy
    if args.https_proxy:
        HTTPS_PROXY = args.https_proxy
    
    if args.generate_playlist:
        success = generate_m3u_playlist(
            args.user, 
            args.password, 
            args.ua, 
            args.timeout, 
            args.output_dir, 
            args.delay,
            args.workers
        )
        return 0 if success else 1
    else:
        parser.print_help()
        return 1

if __name__ == '__main__':
    sys.exit(main())
