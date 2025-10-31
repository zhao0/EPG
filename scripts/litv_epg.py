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
from xml.etree import ElementTree as ET
from xml.dom import minidom

# 全局时区设置
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 代理设置
HTTP_PROXY = os.environ.get('http_proxy', '') or os.environ.get('HTTP_PROXY', '')
HTTPS_PROXY = os.environ.get('https_proxy', '') or os.environ.get('HTTPS_PROXY', '')

PROXIES = {}
if HTTP_PROXY:
    PROXIES['http'] = HTTP_PROXY
if HTTPS_PROXY:
    PROXIES['https'] = HTTPS_PROXY

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.litv.tv/'
}

def create_session():
    """创建带有代理的会话"""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    if PROXIES:
        print(f"使用代理: {PROXIES}")
        session.proxies.update(PROXIES)
    else:
        print("未设置代理，使用直接连接")
    
    return session

def parse_channel_list(session):
    """从LiTV Next.js API获取频道清单，只抓取特定ID模式的频道"""
    print("开始获取LiTV频道清单...")
    
    # LiTV Next.js频道API
    channel_url = "https://www.litv.tv/_next/data/322e31352e3138/channel.json"
    
    try:
        response = session.get(channel_url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # 从 pageProps.introduction.channels 获取频道列表
        channels_data = data.get('pageProps', {}).get('introduction', {}).get('channels', [])
        
        if not channels_data:
            print("❌ 未找到频道数据")
            return []
        
        print(f"找到 {len(channels_data)} 个频道")
        
        # 定义要抓取的频道ID模式
        target_patterns = [
            r'^4gtv-4gtv.*',      # 4gtv-4gtv开头的所有频道
            r'^litv-ftv.*',       # litv-ftv开头的所有频道
            r'^iNEWS$',           # 精确匹配iNEWS
            r'^litv-longturn.*'   # litv-longturn开头的所有频道
        ]
        
        channels = []
        for channel in channels_data:
            channel_name = channel.get('title', '').strip()
            channel_id = channel.get('cdn_code', '').strip()
            
            if not channel_name or not channel_id:
                continue
            
            # 检查频道ID是否符合目标模式
            is_target = False
            for pattern in target_patterns:
                if re.match(pattern, channel_id):
                    is_target = True
                    break
            
            if not is_target:
                continue
                
            # 处理logo URL
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
        
        print(f"✅ 成功获取 {len(channels)} 个目标频道")
        for channel in channels:
            print(f"   - {channel['channelName']} (ID: {channel['id']})")
        return channels
        
    except Exception as e:
        print(f"❌ 获取频道清单失败: {str(e)}")
        return []

def get_epg_from_homepage(session):
    """从LiTV主页Next.js API获取EPG数据"""
    print("开始从主页获取LiTV EPG数据...")
    
    try:
        # 获取主页数据
        main_url = "https://www.litv.tv/_next/data/322e31352e3138/index.json"
        response = session.get(main_url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # 从主页数据中提取节目表
        channel_list = data.get('pageProps', {}).get('homeChannel', {}).get('list', [])
        
        if not channel_list:
            print("❌ 未找到节目表数据")
            return []
        
        print(f"找到 {len(channel_list)} 个频道的节目表")
        
        programs = []
        for channel_data in channel_list:
            channel_id = channel_data.get('contentId', '')
            channel_name = channel_data.get('title', '')
            schedule = channel_data.get('schedule', [])
            
            if not channel_id or not channel_name:
                continue
            
            print(f"处理频道 {channel_name} 的 {len(schedule)} 个节目")
            
            for item in schedule:
                program_data = item.get('program', {})
                air_datetime = item.get('airDateTime', '')
                
                if not air_datetime:
                    continue
                
                try:
                    # 解析UTC时间
                    start_utc = datetime.datetime.strptime(
                        air_datetime, "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=pytz.UTC)
                    
                    # 转换为台北时区
                    start_taipei = start_utc.astimezone(TAIPEI_TZ)
                    
                    # 预设节目时长为1小时
                    duration = datetime.timedelta(hours=1)
                    end_taipei = start_taipei + duration
                    
                    programs.append({
                        "channelName": channel_name,
                        "programName": program_data.get('title', '未知节目'),
                        "description": program_data.get('subTitle', ''),
                        "subtitle": program_data.get('subTitle', ''),
                        "start": start_taipei,
                        "end": end_taipei
                    })
                    
                except ValueError as e:
                    print(f"时间格式解析失败: {air_datetime}, {str(e)}")
                    continue
        
        print(f"✅ 成功获取 {len(programs)} 个节目")
        return programs
        
    except Exception as e:
        print(f"❌ 获取EPG数据失败: {str(e)}")
        return []

def get_epg_from_channel_api(session, channel_id, channel_name):
    """尝试从频道Next.js API获取节目表数据"""
    print(f"尝试从频道API获取 {channel_name} 的节目表...")
    
    # 频道Next.js API
    channel_api_url = f"https://www.litv.tv/_next/data/322e31352e3138/channel/{channel_id}.json"
    
    try:
        response = session.get(channel_api_url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # 检查是否有重定向
        if data.get('pageProps', {}).get('__N_REDIRECT'):
            print(f"⚠️ 频道 {channel_name} 返回重定向")
            return []
        
        # 尝试从不同路径获取节目表
        schedule_paths = [
            data.get('pageProps', {}).get('channel', {}).get('schedule', []),
            data.get('pageProps', {}).get('schedule', []),
            data.get('schedule', [])
        ]
        
        programs = []
        for schedule in schedule_paths:
            if schedule and isinstance(schedule, list):
                print(f"找到节目表数据，共 {len(schedule)} 个项目")
                
                for item in schedule:
                    program_data = item.get('program', {})
                    air_datetime = item.get('airDateTime', '')
                    
                    if not air_datetime:
                        continue
                    
                    try:
                        # 解析UTC时间
                        start_utc = datetime.datetime.strptime(
                            air_datetime, "%Y-%m-%dT%H:%M:%SZ"
                        ).replace(tzinfo=pytz.UTC)
                        
                        # 转换为台北时区
                        start_taipei = start_utc.astimezone(TAIPEI_TZ)
                        
                        # 预设节目时长为1小时
                        duration = datetime.timedelta(hours=1)
                        end_taipei = start_taipei + duration
                        
                        programs.append({
                            "channelName": channel_name,
                            "programName": program_data.get('title', '未知节目'),
                            "description": program_data.get('subTitle', ''),
                            "subtitle": program_data.get('subTitle', ''),
                            "start": start_taipei,
                            "end": end_taipei
                        })
                        
                    except ValueError as e:
                        print(f"时间格式解析失败: {air_datetime}, {str(e)}")
                        continue
                
                if programs:
                    break
        
        print(f"✅ 频道 {channel_name} 获取到 {len(programs)} 个节目")
        return programs
        
    except Exception as e:
        print(f"❌ 获取频道 {channel_name} 节目表失败: {str(e)}")
        return []

def get_litv_epg():
    """获取LiTV电视节目表"""
    print("="*50)
    print("开始获取LiTV电视节目表")
    print("="*50)
    
    # 创建会话
    session = create_session()
    
    # 获取频道清单
    channels_info = parse_channel_list(session)
    if not channels_info:
        print("❌ 无法获取频道清单")
        return [], [], []  # 返回三个空列表
    
    # 从主页获取所有节目表数据
    all_programs = get_epg_from_homepage(session)
    
    # 过滤出目标频道的节目
    target_channel_names = [channel['channelName'] for channel in channels_info]
    filtered_programs = [p for p in all_programs if p['channelName'] in target_channel_names]
    
    # 如果主页数据中没有某些频道的节目，尝试从频道API获取
    missing_channels = []
    for channel in channels_info:
        channel_programs = [p for p in filtered_programs if p['channelName'] == channel['channelName']]
        if not channel_programs:
            missing_channels.append(channel)
    
    if missing_channels:
        print(f"\n尝试从频道API获取 {len(missing_channels)} 个缺失频道的节目...")
        for channel in missing_channels:
            programs = get_epg_from_channel_api(session, channel['id'], channel['channelName'])
            filtered_programs.extend(programs)
            # 添加延迟，避免请求过于频繁
            time.sleep(1)
    
    # 格式化频道资讯（用于XMLTV生成）
    all_channels = []
    for channel in channels_info:
        channel_info = {
            "name": channel["channelName"],
            "channelName": channel["channelName"],
            "id": channel["id"],
            "url": f"https://www.litv.tv/channel/{channel['id']}",
            "source": "litv",
            "desc": channel.get("description", ""),
            "sort": "台湾"
        }
        
        if channel.get("logo"):
            channel_info["logo"] = channel["logo"]
        
        all_channels.append(channel_info)
    
    # 统计结果
    print("\n" + "="*50)
    print(f"✅ 成功获取 {len(all_channels)} 个频道")
    print(f"✅ 成功获取 {len(filtered_programs)} 个节目")
    
    # 按频道名称分组显示节目数量
    channel_counts = {}
    for program in filtered_programs:
        channel_counts[program["channelName"]] = channel_counts.get(program["channelName"], 0) + 1
    
    for channel, count in channel_counts.items():
        print(f"📺 频道 {channel}: {count} 个节目")
    
    print("="*50)
    return channels_info, all_channels, filtered_programs

def generate_xmltv(channels, programs, output_file="litv.xml"):
    """生成XMLTV格式的EPG数据"""
    print(f"\n生成XMLTV档案: {output_file}")
    
    if not channels or not programs:
        print("❌ 没有频道或节目数据，无法生成XMLTV")
        return False
    
    # 建立XML根元素
    root = ET.Element("tv", generator="LITV-EPG-Generator", source="www.litv.tv")
    
    program_count = 0
    for channel in channels:
        channel_name = channel['name']
        
        # 添加频道定义
        channel_elem = ET.SubElement(root, "channel", id=channel_name)
        ET.SubElement(channel_elem, "display-name", lang="zh").text = channel_name
        
        if channel.get('logo'):
            ET.SubElement(channel_elem, "icon", src=channel['logo'])
        
        # 获取该频道的所有节目
        channel_programs = [p for p in programs if p['channelName'] == channel_name]
        if not channel_programs:
            print(f"⚠️ 频道 {channel_name} 没有节目数据")
            continue
            
        # 按开始时间排序
        channel_programs.sort(key=lambda p: p['start'])
        
        # 添加该频道的所有节目
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
                
                title = program.get('programName', '未知节目')
                ET.SubElement(program_elem, "title", lang="zh").text = title
                
                if program.get('description'):
                    ET.SubElement(program_elem, "desc", lang="zh").text = program['description']
                
                program_count += 1
            except Exception as e:
                print(f"⚠️ 跳过无效的节目数据: {str(e)}")
                continue
    
    # 生成XML字符串
    xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')
    
    # 美化XML格式
    try:
        parsed = minidom.parseString(xml_str)
        pretty_xml = parsed.toprettyxml(indent="  ", encoding='utf-8')
    except Exception as e:
        print(f"⚠️ XML美化失败, 使用原始XML: {str(e)}")
        pretty_xml = xml_str.encode('utf-8')
    
    # 储存到档案
    try:
        with open(output_file, 'wb') as f:
            f.write(pretty_xml)
        
        print(f"✅ XMLTV档案已生成: {output_file}")
        print(f"📺 频道数: {len(channels)}")
        print(f"📺 节目数: {program_count}")
        return True
    except Exception as e:
        print(f"❌ 储存XML档案失败: {str(e)}")
        return False

def generate_channel_json(channels_info, output_file="litv.json"):
    """生成JSON格式的频道资讯"""
    print(f"\n生成JSON频道档案: {output_file}")
    
    if not channels_info:
        print("❌ 没有频道数据，无法生成JSON")
        return False
    
    try:
        # 格式化频道资讯为所需的JSON格式
        json_channels = []
        for channel in channels_info:
            json_channel = {
                "channelName": channel["channelName"],
                "id": channel["id"],
                "logo": channel.get("logo", ""),
                "description": channel.get("description", "")
            }
            json_channels.append(json_channel)
        
        # 写入JSON档案
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_channels, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON频道档案已生成: {output_file}")
        print(f"📺 频道数: {len(json_channels)}")
        return True
        
    except Exception as e:
        print(f"❌ 生成JSON频道档案失败: {str(e)}")
        return False

def main():
    """主函数，处理命令行参数"""
    parser = argparse.ArgumentParser(description='LiTV电视节目表')
    parser.add_argument('--output', type=str, default='output/litv.xml', 
                       help='输出XML档案路径 (默认: output/litv.xml)')
    parser.add_argument('--json', type=str, default='output/litv.json',
                       help='输出JSON频道档案路径 (默认: output/litv.json)')
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"建立输出目录: {output_dir}")
    
    json_dir = os.path.dirname(args.json)
    if json_dir and not os.path.exists(json_dir):
        os.makedirs(json_dir, exist_ok=True)
        print(f"建立JSON输出目录: {json_dir}")
    
    try:
        # 获取EPG数据
        channels_info, all_channels, programs = get_litv_epg()
        
        if not channels_info:
            print("❌ 未获取到频道数据，无法生成XML和JSON")
            sys.exit(1)
            
        # 生成XMLTV档案
        if not generate_xmltv(all_channels, programs, args.output):
            print("⚠️ XMLTV档案生成失败，但继续生成JSON档案")
            
        # 生成JSON频道档案
        if not generate_channel_json(channels_info, args.json):
            print("❌ JSON频道档案生成失败")
            sys.exit(1)
            
        print(f"\n🎉 所有档案生成完成！")
        print(f"📄 XMLTV EPG档案: {args.output}")
        print(f"📄 JSON频道档案: {args.json}")
            
    except Exception as e:
        print(f"❌ 主程序错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
