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
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_channel_list():
    """從LiTV API獲取頻道清單"""
    print("開始獲取LiTV頻道清單...")
    
    # LiTV頻道API
    channel_url = "https://www.litv.tv/_next/data/322e31352e3138/channel.json"
    
    try:
        response = requests.get(channel_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        channels_data = data.get('pageProps', {}).get('channels', [])
        
        channels = []
        for channel in channels_data:
            channel_name = channel.get('title', '').strip()
            channel_id = channel.get('cdn_code', '').strip()
            
            if channel_name and channel_id:
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
        
        print(f"✅ 成功獲取 {len(channels)} 個頻道")
        return channels
        
    except Exception as e:
        print(f"❌ 獲取頻道清單失敗: {str(e)}")
        return []

def fetch_epg_data():
    """從LiTV API獲取節目表數據"""
    print("開始獲取LiTV節目表數據...")
    
    # LiTV節目表API
    epg_url = "https://www.litv.tv/_next/data/322e31352e3138/index.json"
    
    try:
        response = requests.get(epg_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return data
        
    except Exception as e:
        print(f"❌ 獲取節目表數據失敗: {str(e)}")
        return None

def parse_epg_data(epg_json, channels_info):
    """解析LiTV節目表數據"""
    if not epg_json:
        return []
    
    programs = []
    
    try:
        channel_list = epg_json.get('pageProps', {}).get('list', [])
        
        for channel_data in channel_list:
            channel_id = channel_data.get('contentId', '')
            schedule = channel_data.get('schedule', [])
            
            # 查找對應的頻道名稱
            channel_name = None
            for channel in channels_info:
                if channel['id'] == channel_id:
                    channel_name = channel['channelName']
                    break
            
            if not channel_name:
                # 如果找不到對應頻道，使用API返回的標題
                channel_name = channel_data.get('title', f"未知頻道-{channel_id}")
                print(f"⚠️ 頻道ID {channel_id} 不在頻道列表中，使用API標題: {channel_name}")
            
            # 解析該頻道的節目表
            for schedule_item in schedule:
                program_data = schedule_item.get('program', {})
                air_datetime = schedule_item.get('airDateTime', '')
                
                if not air_datetime:
                    continue
                
                try:
                    # 解析UTC時間
                    start_utc = datetime.datetime.strptime(
                        air_datetime, "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=pytz.utc)
                    
                    # 轉換為台北時區
                    start_taipei = start_utc.astimezone(TAIPEI_TZ)
                    
                    # 預設節目時長為1小時
                    duration = datetime.timedelta(hours=1)
                    end_taipei = start_taipei + duration
                    
                    programs.append({
                        "channelName": channel_name,
                        "programName": program_data.get('title', '未知節目'),
                        "description": program_data.get('subTitle', ''),
                        "subtitle": program_data.get('subTitle', ''),
                        "start": start_taipei,
                        "end": end_taipei
                    })
                    
                except ValueError as e:
                    print(f"⚠️ 時間格式解析失敗: {air_datetime}, {str(e)}")
                    continue
                
    except Exception as e:
        print(f"❌ 解析節目表數據失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return programs

def get_litv_epg():
    """獲取LiTV電視節目表"""
    print("="*50)
    print("開始獲取LiTV電視節目表")
    print("="*50)
    
    # 獲取頻道清單
    channels_info = parse_channel_list()
    if not channels_info:
        print("❌ 無法獲取頻道清單")
        return [], []
    
    # 獲取節目表數據
    epg_json = fetch_epg_data()
    if not epg_json:
        print("❌ 無法獲取節目表數據")
        return [], []
    
    # 解析節目數據
    programs = parse_epg_data(epg_json, channels_info)
    
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
    print(f"✅ 成功獲取 {len(programs)} 個節目")
    
    # 按頻道名稱分組顯示節目數量
    channel_counts = {}
    for program in programs:
        channel_counts[program["channelName"]] = channel_counts.get(program["channelName"], 0) + 1
    
    for channel, count in channel_counts.items():
        print(f"📺 頻道 {channel}: {count} 個節目")
    
    print("="*50)
    return channels_info, all_channels, programs

def generate_xmltv(channels, programs, output_file="litv.xml"):
    """生成XMLTV格式的EPG數據"""
    print(f"\n生成XMLTV檔案: {output_file}")
    
    # 建立XML根元素
    root = ET.Element("tv", generator="LITV-EPG-Generator", source="www.litv.tv")
    
    # 頻道1 -> 頻道1節目 -> 頻道2-> 頻道2節目 -> ...
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
                
                if program.get('subtitle'):
                    ET.SubElement(program_elem, "sub-title", lang="zh").text = program['subtitle']
                
                if program.get('description'):
                    ET.SubElement(program_elem, "desc", lang="zh").text = program['description']
                
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
        print(f"💾 檔案大小: {os.path.getsize(output_file) / 1024:.2f} KB")
        return True
    except Exception as e:
        print(f"❌ 儲存XML檔案失敗: {str(e)}")
        return False

def generate_channel_json(channels_info, output_file="litv.json"):
    """生成JSON格式的頻道資訊"""
    print(f"\n生成JSON頻道檔案: {output_file}")
    
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
        print(f"💾 檔案大小: {os.path.getsize(output_file) / 1024:.2f} KB")
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
        
        if not channels_info or not programs:
            print("❌ 未獲取到有效EPG數據，無法生成XML和JSON")
            sys.exit(1)
            
        # 生成XMLTV檔案
        if not generate_xmltv(all_channels, programs, args.output):
            sys.exit(1)
            
        # 生成JSON頻道檔案
        if not generate_channel_json(channels_info, args.json):
            sys.exit(1)
            
        print(f"\n🎉 所有檔案生成完成！")
        print(f"📄 XMLTV EPG檔案: {args.output}")
        print(f"📄 JSON頻道檔案: {args.json}")
            
    except Exception as e:
        print(f"❌ 主程序錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
