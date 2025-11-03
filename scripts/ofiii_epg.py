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
    """解析頻道清單檔案內容"""
    channel_list = [
        "nnews-zh",
        "4gtv-4gtv009",
        "4gtv-4gtv066",
        "4gtv-4gtv040",
        "4gtv-4gtv041",
        "4gtv-4gtv051",
        "4gtv-4gtv052",
        "4gtv-4gtv074",
        "4gtv-4gtv084",
        "4gtv-4gtv085",
        "4gtv-4gtv076",
        "4gtv-4gtv102",
        "4gtv-4gtv103",
        "4gtv-4gtv104",
        "4gtv-4gtv156",
        "4gtv-4gtv158",
        "litv-ftv16",
        "litv-ftv17",
        "litv-longturn01",
        "litv-longturn02",
        "litv-longturn03",
        "litv-longturn11",
        "litv-longturn12",
        "litv-longturn14",
        "litv-longturn18",
        "litv-longturn19",
        "litv-longturn20",
        "litv-longturn21",
        "litv-longturn22",
        "iNEWS",
        "daystar",
        "ofiii13",
        "ofiii16",
        "ofiii22",
        "ofiii23",
        "ofiii24",
        "ofiii31",
        "ofiii32",
        "ofiii36",
        "ofiii38",
        "ofiii39",
        "ofiii1048",
        "ofiii50",
        "ofiii55",
        "ofiii64",
        "ofiii70",
        "ofiii73",
        "ofiii74",
        "ofiii75",
        "ofiii76",
        "ofiii81",
        "ofiii82",
        "ofiii83",
        "ofiii85",
        "ofiii88",
        "ofiii89",
        "ofiii91",
        "ofiii92",
        "ofiii94",
        "ofiii95",
        "ofiii96",
        "ofiii97",
        "ofiii99",
        "ofiii100",
        "ofiii101",
        "ofiii102",
        "ofiii103",
        "ofiii104",
        "ofiii105",
        "ofiii106",
        "ofiii107",
        "ofiii108",
        "ofiii109",
        "ofiii110",
        "ofiii111",
        "ofiii112",
        "ofiii113",
        "ofiii114",
        "ofiii115",
        "ofiii116",
        "ofiii117",
        "ofiii118",
        "ofiii119",
        "ofiii120",
        "ofiii121",
        "ofiii122",
        "ofiii123",
        "ofiii124",
        "ofiii125",
        "ofiii126",
        "ofiii127",
        "ofiii128",
        "ofiii129",
        "ofiii131",
        "ofiii132",
        "ofiii133",
        "ofiii134",
        "ofiii135",
        "ofiii136",
        "ofiii137",
        "ofiii139",
        "ofiii140",
        "ofiii141",
        "ofiii142",
        "ofiii143",
        "ofiii144",
        "ofiii145",
        "ofiii146",
        "ofiii147",
        "ofiii148",
        "ofiii150",
        "ofiii151",
        "ofiii152",
        "ofiii153",
        "ofiii154",
        "ofiii155",
        "ofiii156",
        "ofiii157",
        "ofiii158",
        "ofiii159",
        "ofiii160",
        "ofiii161",
        "ofiii162",
        "ofiii163",
        "ofiii164",
        "ofiii165",
        "ofiii166",
        "ofiii167",
        "ofiii168",
        "ofiii169",
        "ofiii170",
        "ofiii171",
        "ofiii172",
        "ofiii173",
        "ofiii174",
        "ofiii175",
        "ofiii177",
        "ofiii178",
        "ofiii179",
        "ofiii180",
        "ofiii182",
        "ofiii183",
        "ofiii184",
        "ofiii185",
        "ofiii186",
        "ofiii187",
        "ofiii192",
        "ofiii195",
        "ofiii196",
        "ofiii198",
        "ofiii200",
        "ofiii201",
        "ofiii202",
        "ofiii203",
        "ofiii204",
        "ofiii205",
        "ofiii206",
        "ofiii207",
        "ofiii208",
        "ofiii209",
        "ofiii210",
        "ofiii211",
        "ofiii212",
        "ofiii215",
        "ofiii216",
        "ofiii217",
        "ofiii218",
        "ofiii225",
        "ofiii226",
        "ofiii227",
        "ofiii228",
        "ofiii234",
        "ofiii235",
        "ofiii236",
        "ofiii237",
        "ofiii238",
        "ofiii239",
        "ofiii240",
        "ofiii241",
        "ofiii242",
        "ofiii243",
        "ofiii244",
        "ofiii245",
        "ofiii246",
        "ofiii247",
        "ofiii248",
        "ofiii250",
        "ofiii251",
        "ofiii252",
        "ofiii254",
        "ofiii255"
    ]
    
    return channel_list

def fetch_epg_data(channel_id, max_retries=3):
    """獲取指定頻道的電視節目表數據"""
    url = f"https://www.ofiii.com/channel/watch/{channel_id}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            
            if not response.text.strip():
                print(f"⚠️ 響應內容為空: {channel_id}")
                return None
                
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tag = soup.find('script', id='__NEXT_DATA__')
            
            if script_tag and script_tag.string:
                try:
                    return json.loads(script_tag.string)
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON解析失敗: {channel_id}, {str(e)}")
                    return None
            else:
                print(f"⚠️ 未找到__NEXT_DATA__標簽: {channel_id}")
                return None
                
        except requests.RequestException as e:
            wait_time = random.uniform(1, 3) * (attempt + 1)
            print(f"⚠️ 請求失敗 (嘗試 {attempt+1}/{max_retries}), 等待 {wait_time:.2f}秒: {str(e)}")
            time.sleep(wait_time)
    
    print(f"❌ 無法獲取 電視節目表 數據: {channel_id}")
    return None

def parse_live_epg_data(json_data, channel_id):
    """解析直播頻道的電視節目表 JSON數據"""
    if not json_data:
        return []
    
    programs = []
    try:
        if not json_data.get('props') or not json_data['props'].get('pageProps') or not json_data['props']['pageProps'].get('channel'):
            print(f"❌ JSON結構無效: {channel_id}")
            return []
        
        schedule = json_data['props']['pageProps']['channel'].get('Schedule', [])
        
        for item in schedule:
            try:
                start_utc = datetime.datetime.strptime(
                    item['AirDateTime'], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=pytz.utc)
                start_taipei = start_utc.astimezone(TAIPEI_TZ)
                
                duration = datetime.timedelta(seconds=item.get('Duration', 0))
                end_taipei = start_taipei + duration
                
                program_info = item.get('program', {})
                
                programs.append({
                    "channelName": channel_id,
                    "programName": program_info.get('Title', '未知節目'),
                    "description": program_info.get('Description', ''),
                    "subtitle": program_info.get('SubTitle', ''),
                    "start": start_taipei,
                    "end": end_taipei
                })
                
            except (KeyError, ValueError, TypeError) as e:
                print(f"⚠️ 跳過無效的節目數據: {channel_id}, {str(e)}")
                continue
                
    except (KeyError, TypeError, ValueError) as e:
        print(f"❌ 解析直播電視節目表數據失敗: {str(e)}")
    
    return programs

def parse_vod_epg_data(json_data, channel_id):
    """解析點播頻道的電視節目表 JSON數據"""
    if not json_data:
        return []
    
    programs = []
    try:
        if not json_data.get('props') or not json_data['props'].get('pageProps') or not json_data['props']['pageProps'].get('channel'):
            print(f"❌ JSON結構無效: {channel_id}")
            return []
        
        channel_data = json_data['props']['pageProps']['channel']
        vod_schedule = channel_data.get('vod_channel_schedule', {})
        
        if not vod_schedule:
            print(f"⚠️ 點播頻道 {channel_id} 沒有節目表數據")
            return []
        
        vod_programs = vod_schedule.get('programs', [])
        
        for item in vod_programs:
            try:
                start_timestamp = item.get('p_start', 0)
                if start_timestamp == 0:
                    continue
                    
                start_taipei = datetime.datetime.fromtimestamp(start_timestamp / 1000, TAIPEI_TZ)
                
                duration_ms = item.get('length', 0)
                duration = datetime.timedelta(milliseconds=duration_ms)
                end_taipei = start_taipei + duration
                
                programs.append({
                    "channelName": channel_id,
                    "programName": item.get('title', '未知節目'),
                    "description": item.get('vod_channel_description', ''),
                    "subtitle": item.get('subtitle', ''),
                    "start": start_taipei,
                    "end": end_taipei
                })
                
            except (KeyError, ValueError, TypeError) as e:
                print(f"⚠️ 跳過無效的時間格式: {channel_id}, {str(e)}")
                continue
            
    except (KeyError, TypeError, ValueError) as e:
        print(f"❌ 解析點播電視節目表數據失敗: {str(e)}")
    
    return programs

def parse_epg_data(json_data, channel_id):
    """解析電視節目表 JSON數據，自動判斷直播或點播"""
    if not json_data:
        return []
    
    try:
        channel_data = json_data['props']['pageProps']['channel']
        content_type = channel_data.get('content_type', '')
        
        if content_type == 'vod-channel' or channel_data.get('vod_channel_schedule'):
            print(f"📹 檢測到點播頻道: {channel_id}")
            return parse_vod_epg_data(json_data, channel_id)
        else:
            print(f"📺 檢測到直播頻道: {channel_id}")
            return parse_live_epg_data(json_data, channel_id)
            
    except (KeyError, TypeError, ValueError) as e:
        print(f"❌ 判斷頻道類型失敗: {str(e)}")
        return parse_live_epg_data(json_data, channel_id)

def get_channel_info(json_data, channel_id):
    """從JSON數據中提取頻道信息"""
    if not json_data:
        return None
    
    try:
        page_props = json_data.get('props', {}).get('pageProps', {})
        channel_data = page_props.get('channel', {})
        
        # 獲取頻道名稱
        channel_name = channel_data.get('title', channel_id)
        
        # 獲取頻道logo
        logo = channel_data.get('picture', '')
        if logo and not logo.startswith("http"):
            logo = f"https://p-cdnstatic.svc.litv.tv/{logo}"
            # 將logo路徑中的_tv替換為_mobile以獲取移動版logo
            if '_tv' in logo:
                logo = logo.replace('_tv', '_mobile')
        
        # 獲取頻道描述
        description = channel_data.get('description', '')
        
        return {
            "channelName": channel_name,
            "id": channel_id,
            "logo": logo,
            "description": description
        }
    except Exception as e:
        print(f"❌ 提取頻道信息失敗: {channel_id}, {str(e)}")
        return None

def get_ofiii_epg():
    """獲取歐飛電視節目表"""
    print("="*50)
    print("開始獲取歐飛電視節目表")
    print("="*50)
    
    # 獲取頻道清單
    channels = parse_channel_list()
    if not channels:
        print("❌ 無法解析頻道清單")
        return [], []
    
    all_channels_info = []
    all_programs = []
    failed_channels = []
    
    # 遍歷所有頻道
    for idx, channel_id in enumerate(channels):
        print(f"\n處理頻道 [{idx+1}/{len(channels)}]: {channel_id}")
        
        # 獲取EPG數據
        json_data = fetch_epg_data(channel_id)
        if not json_data:
            failed_channels.append(channel_id)
            continue
            
        # 提取頻道信息
        channel_info = get_channel_info(json_data, channel_id)
        if channel_info:
            all_channels_info.append(channel_info)
        
        # 解析節目數據
        programs = parse_epg_data(json_data, channel_id)
        all_programs.extend(programs)
            
        # 隨機延遲
        if idx < len(channels) - 1:
            delay = random.uniform(1, 3)
            print(f"⏱️ 隨機延遲 {delay:.2f}秒")
            time.sleep(delay)
    
    # 統計結果
    print("\n" + "="*50)
    print(f"✅ 成功獲取 {len(all_channels_info)} 個頻道信息")
    print(f"✅ 成功獲取 {len(all_programs)} 個節目")
    
    if failed_channels:
        print(f"⚠️ 失敗頻道 ({len(failed_channels)}): {', '.join(failed_channels)}")
    
    channel_counts = {}
    for program in all_programs:
        channel_counts[program["channelName"]] = channel_counts.get(program["channelName"], 0) + 1
    
    for channel, count in channel_counts.items():
        print(f"📺 頻道 {channel}: {count} 個節目")
    
    print("="*50)
    return all_channels_info, all_programs

def generate_xmltv(channels_info, programs, output_file="ofiii.xml"):
    """生成XMLTV格式的EPG數據"""
    print(f"\n生成XMLTV檔案: {output_file}")
    
    root = ET.Element("tv", generator="OFIII-EPG-Generator", source="www.ofiii.com")
    
    # 添加頻道定義
    for channel in channels_info:
        channel_id = channel['id']
        channel_name = channel['channelName']
        
        channel_elem = ET.SubElement(root, "channel", id=channel_id)
        ET.SubElement(channel_elem, "display-name", lang="zh").text = channel_name
        
        if channel.get('logo'):
            ET.SubElement(channel_elem, "icon", src=channel['logo'])
        
        # 添加頻道描述到XMLTV
        if channel.get('description'):
            ET.SubElement(channel_elem, "desc", lang="zh").text = channel['description']
    
    # 添加節目
    program_count = 0
    for program in programs:
        try:
            channel_id = program['channelName']
            start_time = program['start'].strftime('%Y%m%d%H%M%S %z')
            end_time = program['end'].strftime('%Y%m%d%H%M%S %z')
            
            program_elem = ET.SubElement(
                root, 
                "programme", 
                channel=channel_id,
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
    
    # 生成XML
    xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')
    
    try:
        parsed = minidom.parseString(xml_str)
        pretty_xml = parsed.toprettyxml(indent="  ", encoding='utf-8')
    except Exception as e:
        print(f"⚠️ XML美化失敗, 使用原始XML: {str(e)}")
        pretty_xml = xml_str.encode('utf-8')
    
    try:
        with open(output_file, 'wb') as f:
            f.write(pretty_xml)
        
        print(f"✅ XMLTV檔案已生成: {output_file}")
        print(f"📺 頻道數: {len(channels_info)}")
        print(f"📺 節目數: {program_count}")
        print(f"💾 檔案大小: {os.path.getsize(output_file) / 1024:.2f} KB")
        return True
    except Exception as e:
        print(f"❌ 儲存XML檔案失敗: {str(e)}")
        return False

def generate_json_file(channels_info, output_file="ofiii.json"):
    """生成JSON格式的頻道數據"""
    print(f"\n生成JSON檔案: {output_file}")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(channels_info, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON檔案已生成: {output_file}")
        print(f"📺 頻道數: {len(channels_info)}")
        print(f"💾 檔案大小: {os.path.getsize(output_file) / 1024:.2f} KB")
        
        # 顯示前幾個頻道作為示例
        print("\nJSON檔案前5個頻道示例:")
        for i, channel in enumerate(channels_info[:5]):
            print(f"  {i+1}. {channel}")
            
        return True
    except Exception as e:
        print(f"❌ 儲存JSON檔案失敗: {str(e)}")
        return False

def main():
    """主函數，處理命令行參數"""
    parser = argparse.ArgumentParser(description='歐飛電視節目表')
    parser.add_argument('--output', type=str, default='output/ofiii.xml', 
                       help='輸出XML檔案路徑 (默認: output/ofiii.xml)')
    
    args = parser.parse_args()
    
    # 確保輸出目錄存在
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"建立輸出目錄: {output_dir}")
    
    try:
        # 獲取EPG數據
        channels_info, programs = get_ofiii_epg()
        
        if not channels_info:
            print("❌ 未獲取到有效頻道信息，無法生成檔案")
            sys.exit(1)
            
        # 生成XMLTV檔案
        xml_output = args.output
        if not generate_xmltv(channels_info, programs, xml_output):
            sys.exit(1)
            
        # 生成JSON檔案
        json_output = os.path.join(output_dir, "ofiii.json")
        if not generate_json_file(channels_info, json_output):
            print("⚠️ JSON檔案生成失敗，但XML已成功生成")
            
    except Exception as e:
        print(f"❌ 主程序錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
