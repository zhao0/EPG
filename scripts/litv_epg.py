import os
import sys
import re
import json
import time
import random
import argparse
import requests
import datetime
import pytz
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET
from xml.dom import minidom

# 全局時區設置
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 代理設置 (從環境變量讀取)
HTTP_PROXY = os.environ.get('http_proxy', '') or os.environ.get('HTTP_PROXY', '')
HTTPS_PROXY = os.environ.get('https_proxy', '') or os.environ.get('HTTPS_PROXY', '')

PROXIES = {}
if HTTP_PROXY:
    PROXIES['http'] = HTTP_PROXY
if HTTPS_PROXY:
    PROXIES['https'] = HTTPS_PROXY

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def create_session():
    """創建帶有代理的會話"""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    if PROXIES:
        print(f"使用代理: {PROXIES}")
        session.proxies.update(PROXIES)
    else:
        print("未設置代理，使用直接連接")
    
    return session

def parse_channel_list(session):
    """從LiTV API獲取頻道清單，只抓取特定ID模式的頻道"""
    print("開始獲取LiTV頻道清單...")
    
    # LiTV頻道API
    channel_url = "https://www.litv.tv/_next/data/322e31352e3138/channel.json"
    
    try:
        response = session.get(channel_url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # 從 pageProps.introduction.channels 獲取頻道列表
        channels_data = data.get('pageProps', {}).get('introduction', {}).get('channels', [])
        
        if not channels_data:
            print("❌ 未找到頻道數據")
            return []
        
        print(f"找到 {len(channels_data)} 個頻道")
        
        # 定義要抓取的頻道ID模式
        target_patterns = [
            r'^4gtv-4gtv.*',      # 4gtv-4gtv開頭的所有頻道
            r'^litv-ftv.*',       # litv-ftv開頭的所有頻道
            r'^iNEWS$',           # 精確匹配iNEWS
            r'^litv-longturn.*'   # litv-longturn開頭的所有頻道
        ]
        
        channels = []
        for channel in channels_data:
            channel_name = channel.get('title', '').strip()
            channel_id = channel.get('cdn_code', '').strip()
            
            if not channel_name or not channel_id:
                continue
            
            # 檢查頻道ID是否符合目標模式
            is_target = False
            for pattern in target_patterns:
                if re.match(pattern, channel_id):
                    is_target = True
                    break
            
            if not is_target:
                continue
                
            # 處理logo URL
            logo = channel.get('picture', '')
            if logo and not logo.startswith('http'):
                logo = f"https://fino.svc.litv.tv/{logo.lstrip('/')}"
            
            channels.append({
                "channelName": channel_name,
                "id": channel_id,
                "logo": logo,
                "description": channel.get('description', ''),
                "content_type": channel.get('content_type', 'channel')
            })
        
        print(f"✅ 成功獲取 {len(channels)} 個目標頻道")
        for channel in channels:
            print(f"   - {channel['channelName']} (ID: {channel['id']})")
        return channels
        
    except Exception as e:
        print(f"❌ 獲取頻道清單失敗: {str(e)}")
        return []

def fetch_channel_epg(session, channel_id, channel_name):
    """從頻道頁面獲取節目表數據"""
    print(f"\n開始獲取頻道 {channel_name} 的節目表...")
    
    # 頻道頁面URL
    channel_url = f"https://www.litv.tv/channel/watch/{channel_id}"
    
    try:
        response = session.get(channel_url, timeout=30)
        response.raise_for_status()
        
        # 使用正則表達式直接從HTML中提取節目資訊
        html_content = response.text
        
        # 尋找節目表區域 - 根據您提供的HTML結構
        # 查找包含日期和節目資訊的區域
        programs = []
        
        # 獲取當前日期
        now = datetime.datetime.now(TAIPEI_TZ)
        
        # 查找所有日期標題和節目行
        date_pattern = r'<div[^>]*class="[^"]*pl-\[10px\][^"]*pr-\[10px\][^"]*text-\[15px\][^"]*text-\[#fff\][^"]*leading-\[40px\][^"]*"[^>]*>([^<]+)</div>'
        program_pattern = r'<div[^>]*class="[^"]*pl-\[10px\][^"]*grow[^"]*text-\[15px\][^"]*leading-\[30px\][^"]*[^>]*>([^<]+)</div>'
        
        dates = re.findall(date_pattern, html_content)
        program_texts = re.findall(program_pattern, html_content)
        
        print(f"找到 {len(dates)} 個日期標題")
        print(f"找到 {len(program_texts)} 個節目文本")
        
        # 解析日期和節目
        current_date = None
        program_index = 0
        
        for date_text in dates:
            print(f"處理日期: {date_text}")
            
            # 解析日期
            date_parts = date_text.split(' / ')
            if len(date_parts) >= 2:
                date_str = date_parts[1]  # 例如 "11月1日"
                
                # 將日期轉換為當前年份的完整日期
                current_year = now.year
                try:
                    # 解析 "月日" 格式
                    month_day_match = re.search(r'(\d+)月(\d+)日', date_str)
                    if month_day_match:
                        month = int(month_day_match.group(1))
                        day = int(month_day_match.group(2))
                        current_date = datetime.datetime(current_year, month, day, tzinfo=TAIPEI_TZ)
                        print(f"解析日期: {current_year}-{month}-{day}")
                except Exception as e:
                    print(f"日期解析失敗: {date_str}, {str(e)}")
                    continue
            
            # 處理這個日期下的節目
            while program_index < len(program_texts):
                program_text = program_texts[program_index]
                
                # 檢查是否是下一個日期標題（節目文本中不會包含日期格式）
                if re.search(r'\d+月\d+日', program_text):
                    break
                
                # 解析節目時間和名稱
                time_match = re.match(r'(\d{1,2}):(\d{2})\s+(.+)', program_text)
                if time_match and current_date:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2))
                    program_name = time_match.group(3)
                    
                    # 計算節目開始時間
                    program_start = current_date.replace(hour=hour, minute=minute, second=0)
                    
                    # 預設節目時長為1小時
                    program_end = program_start + datetime.timedelta(hours=1)
                    
                    programs.append({
                        "channelName": channel_name,
                        "programName": program_name,
                        "description": "",
                        "subtitle": "",
                        "start": program_start,
                        "end": program_end
                    })
                    
                    print(f"  節目: {hour:02d}:{minute:02d} - {program_name}")
                
                program_index += 1
        
        print(f"✅ 頻道 {channel_name} 獲取到 {len(programs)} 個節目")
        return programs
        
    except Exception as e:
        print(f"❌ 獲取頻道 {channel_name} 節目表失敗: {str(e)}")
        return []

def get_litv_epg():
    """獲取LiTV電視節目表"""
    print("="*50)
    print("開始獲取LiTV電視節目表")
    print("="*50)
    
    # 創建會話
    session = create_session()
    
    # 獲取頻道清單
    channels_info = parse_channel_list(session)
    if not channels_info:
        print("❌ 無法獲取頻道清單")
        return [], [], []  # 返回三個空列表
    
    # 為每個頻道獲取節目表
    all_programs = []
    for channel in channels_info:
        channel_id = channel["id"]
        channel_name = channel["channelName"]
        
        # 獲取該頻道的節目表
        programs = fetch_channel_epg(session, channel_id, channel_name)
        all_programs.extend(programs)
        
        # 添加隨機延遲，避免請求過於頻繁
        delay = random.uniform(2, 5)
        print(f"等待 {delay:.1f} 秒後繼續...")
        time.sleep(delay)
    
    # 格式化頻道資訊（用於XMLTV生成）
    all_channels = []
    for channel in channels_info:
        channel_info = {
            "name": channel["channelName"],
            "channelName": channel["channelName"],
            "id": channel["id"],
            "url": f"https://www.litv.tv/channel/{channel['id']}",
            "source": "litv",
            "desc": channel.get("description", ""),
            "sort": "台灣"
        }
        
        if channel.get("logo"):
            channel_info["logo"] = channel["logo"]
        
        all_channels.append(channel_info)
    
    # 統計結果
    print("\n" + "="*50)
    print(f"✅ 成功獲取 {len(all_channels)} 個頻道")
    print(f"✅ 成功獲取 {len(all_programs)} 個節目")
    
    # 按頻道名稱分組顯示節目數量
    channel_counts = {}
    for program in all_programs:
        channel_counts[program["channelName"]] = channel_counts.get(program["channelName"], 0) + 1
    
    for channel, count in channel_counts.items():
        print(f"📺 頻道 {channel}: {count} 個節目")
    
    print("="*50)
    return channels_info, all_channels, all_programs

def generate_xmltv(channels, programs, output_file="litv.xml"):
    """生成XMLTV格式的EPG數據"""
    print(f"\n生成XMLTV檔案: {output_file}")
    
    if not channels or not programs:
        print("❌ 沒有頻道或節目數據，無法生成XMLTV")
        return False
    
    # 建立XML根元素
    root = ET.Element("tv", generator="LITV-EPG-Generator", source="www.litv.tv")
    
    program_count = 0
    for channel in channels:
        channel_name = channel['name']
        
        # 添加頻道定義
        channel_elem = ET.SubElement(root, "channel", id=channel_name)
        ET.SubElement(channel_elem, "display-name", lang="zh").text = channel_name
        
        if channel.get('logo'):
            ET.SubElement(channel_elem, "icon", src=channel['logo'])
        
        # 獲取該頻道的所有節目
        channel_programs = [p for p in programs if p['channelName'] == channel_name]
        if not channel_programs:
            print(f"⚠️ 頻道 {channel_name} 沒有節目數據")
            continue
            
        # 按開始時間排序
        channel_programs.sort(key=lambda p: p['start'])
        
        # 添加該頻道的所有節目
        for program in channel_programs:
            try:
                start_time = program['start'].strftime('%Y%m%d%H%M%S %z')
                end_time = program['end'].strftime('%Y%m%d%H%M%S %z')
                
                program_elem = ET.SubElement(
                    root, 
                    "programme", 
                    channel=channel_name,
                    start=start_time, 
                    stop=end_time
                )
                
                title = program.get('programName', '未知節目')
                ET.SubElement(program_elem, "title", lang="zh").text = title
                
                program_count += 1
            except Exception as e:
                print(f"⚠️ 跳過無效的節目數據: {str(e)}")
                continue
    
    # 生成XML字符串
    xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')
    
    # 美化XML格式
    try:
        parsed = minidom.parseString(xml_str)
        pretty_xml = parsed.toprettyxml(indent="  ", encoding='utf-8')
    except Exception as e:
        print(f"⚠️ XML美化失敗, 使用原始XML: {str(e)}")
        pretty_xml = xml_str.encode('utf-8')
    
    # 儲存到檔案
    try:
        with open(output_file, 'wb') as f:
            f.write(pretty_xml)
        
        print(f"✅ XMLTV檔案已生成: {output_file}")
        print(f"📺 頻道數: {len(channels)}")
        print(f"📺 節目數: {program_count}")
        return True
    except Exception as e:
        print(f"❌ 儲存XML檔案失敗: {str(e)}")
        return False

def generate_channel_json(channels_info, output_file="litv.json"):
    """生成JSON格式的頻道資訊"""
    print(f"\n生成JSON頻道檔案: {output_file}")
    
    if not channels_info:
        print("❌ 沒有頻道數據，無法生成JSON")
        return False
    
    try:
        # 格式化頻道資訊為所需的JSON格式
        json_channels = []
        for channel in channels_info:
            json_channel = {
                "channelName": channel["channelName"],
                "id": channel["id"],
                "logo": channel.get("logo", ""),
                "description": channel.get("description", "")
            }
            json_channels.append(json_channel)
        
        # 寫入JSON檔案
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_channels, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON頻道檔案已生成: {output_file}")
        print(f"📺 頻道數: {len(json_channels)}")
        return True
        
    except Exception as e:
        print(f"❌ 生成JSON頻道檔案失敗: {str(e)}")
        return False

def main():
    """主函數，處理命令行參數"""
    parser = argparse.ArgumentParser(description='LiTV電視節目表')
    parser.add_argument('--output', type=str, default='output/litv.xml', 
                       help='輸出XML檔案路徑 (默認: output/litv.xml)')
    parser.add_argument('--json', type=str, default='output/litv.json',
                       help='輸出JSON頻道檔案路徑 (默認: output/litv.json)')
    
    args = parser.parse_args()
    
    # 確保輸出目錄存在
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"建立輸出目錄: {output_dir}")
    
    json_dir = os.path.dirname(args.json)
    if json_dir and not os.path.exists(json_dir):
        os.makedirs(json_dir, exist_ok=True)
        print(f"建立JSON輸出目錄: {json_dir}")
    
    try:
        # 獲取EPG數據
        channels_info, all_channels, programs = get_litv_epg()
        
        if not channels_info:
            print("❌ 未獲取到頻道數據，無法生成XML和JSON")
            sys.exit(1)
            
        # 生成XMLTV檔案
        if not generate_xmltv(all_channels, programs, args.output):
            print("⚠️ XMLTV檔案生成失敗，但繼續生成JSON檔案")
            
        # 生成JSON頻道檔案
        if not generate_channel_json(channels_info, args.json):
            print("❌ JSON頻道檔案生成失敗")
            sys.exit(1)
            
        print(f"\n🎉 所有檔案生成完成！")
        print(f"📄 XMLTV EPG檔案: {args.output}")
        print(f"📄 JSON頻道檔案: {args.json}")
            
    except Exception as e:
        print(f"❌ 主程序錯誤: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
