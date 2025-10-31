import requests
import json
import time
import os
from pathlib import Path

def get_channel_data(channel_id):
    """獲取頻道資料"""
    url = f"https://www.ofiii.com/_next/data/464M-DArabIf4rNleEdJm/channel/watch/{channel_id}.json"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ 獲取頻道 {channel_id} 資料失敗: {e}")
        return None

def generate_m3u_content(channel_data, channel_id):
    """生成M3U內容"""
    m3u_lines = []
    
    try:
        page_props = channel_data.get('pageProps', {})
        channel_info = page_props.get('channel', {})
        
        if not channel_info:
            print(f"⚠️  頻道 {channel_id} 沒有channel資訊")
            return m3u_lines
        
        # 基本頻道資訊
        name = channel_info.get('title', 'Unknown')
        picture = channel_info.get('picture', '')
        content_id = channel_info.get('content_id', channel_id)
        
        # 獲取節目列表
        schedule = channel_info.get('vod_channel_schedule', {})
        programs = schedule.get('programs', [])
        
        if not programs:
            print(f"ℹ️  頻道 {name} 沒有節目列表，跳過")
            return m3u_lines
        
        print(f"📺 處理頻道: {name} ({channel_id}) - 找到 {len(programs)} 個節目")
        
        for program in programs:
            asset_id = program.get('asset_id', '')
            title = program.get('title', '')
            subtitle = program.get('subtitle', '')
            
            if not asset_id:
                continue
                
            # 生成M3U條目
            extinf_line = f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" tvg-logo="https://p-cdnstatic.svc.litv.tv/{picture}" group-title="{name}",{title}-{subtitle}'
            url_line = f'http://localhost:5050/play/{content_id}&{asset_id}/index.m3u8'
            
            m3u_lines.append(extinf_line)
            m3u_lines.append(url_line)
            
    except Exception as e:
        print(f"❌ 處理頻道 {channel_id} 資料時發生錯誤: {e}")
    
    return m3u_lines

def ensure_output_dir():
    """確保輸出目錄存在"""
    output_dir = Path('../output')
    output_dir.mkdir(exist_ok=True)
    return output_dir

def main():
    # 確保輸出目錄存在
    output_dir = ensure_output_dir()
    output_file = output_dir / 'playlist.m3u'
    
    # 頻道ID列表
    channel_ids = [
        "daystar","ofiii13","ofiii16","ofiii22","ofiii23","ofiii24","ofiii31","ofiii32",
        "ofiii36","ofiii38","ofiii39","ofiii1048","ofiii50","ofiii55","ofiii64","ofiii70",
        "ofiii73","ofiii74","ofiii75","ofiii76","ofiii81","ofiii82","ofiii83","ofiii85",
        "ofiii88","ofiii89","ofiii91","ofiii92","ofiii94","ofiii95","ofiii96","ofiii97",
        "ofiii99","ofiii100","ofiii101","ofiii102","ofiii103","ofiii104","ofiii105",
        "ofiii106","ofiii107","ofiii108","ofiii109","ofiii110","ofiii111","ofiii112",
        "ofiii113","ofiii114","ofiii115","ofiii116","ofiii117","ofiii118","ofiii119",
        "ofiii120","ofiii121","ofiii122","ofiii123","ofiii124","ofiii125","ofiii126",
        "ofiii127","ofiii128","ofiii129","ofiii131","ofiii132","ofiii133","ofiii134",
        "ofiii135","ofiii136","ofiii137","ofiii139","ofiii140","ofiii141","ofiii142",
        "ofiii143","ofiii144","ofiii145","ofiii146","ofiii147","ofiii148","ofiii150",
        "ofiii151","ofiii152","ofiii153","ofiii154","ofiii155","ofiii156","ofiii157",
        "ofiii158","ofiii159","ofiii160","ofiii161","ofiii162","ofiii163","ofiii164",
        "ofiii165","ofiii166","ofiii167","ofiii168","ofiii169","ofiii170","ofiii171",
        "ofiii172","ofiii173","ofiii174","ofiii175","ofiii177","ofiii178","ofiii179",
        "ofiii180","ofiii182","ofiii183","ofiii184","ofiii185","ofiii186","ofiii187",
        "ofiii192","ofiii195","ofiii196","ofiii198","ofiii200","ofiii201","ofiii202",
        "ofiii203","ofiii204","ofiii205","ofiii206","ofiii207","ofiii208","ofiii209",
        "ofiii210","ofiii211","ofiii212","ofiii215","ofiii216","ofiii217","ofiii218",
        "ofiii225","ofiii226","ofiii227","ofiii228","ofiii234","ofiii235","ofiii236",
        "ofiii237","ofiii238","ofiii239","ofiii240","ofiii241","ofiii242","ofiii243",
        "ofiii244","ofiii245","ofiii246","ofiii247","ofiii248","ofiii250","ofiii251",
        "ofiii252","ofiii254","ofiii255"
    ]
    
    # M3U文件頭
    m3u_content = ['#EXTM3U x-tvg-url=""']
    
    print("🚀 開始獲取頻道資料...")
    successful_channels = 0
    failed_channels = 0
    skipped_channels = 0
    
    # 遍歷所有頻道ID
    for i, channel_id in enumerate(channel_ids, 1):
        print(f"\n📋 處理頻道 {i}/{len(channel_ids)}: {channel_id}")
        
        # 獲取頻道資料
        channel_data = get_channel_data(channel_id)
        
        if channel_data:
            # 生成M3U內容
            channel_lines = generate_m3u_content(channel_data, channel_id)
            
            if channel_lines:
                m3u_content.extend(channel_lines)
                successful_channels += 1
                print(f"✅ 成功添加頻道 {channel_id}")
            else:
                skipped_channels += 1
        else:
            failed_channels += 1
        
        # 添加延遲避免請求過快
        time.sleep(0.5)
    
    # 寫入M3U文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_content))
    
    print(f"\n🎉 M3U文件生成完成！")
    print(f"📊 統計資訊:")
    print(f"   ✅ 成功處理: {successful_channels} 個頻道")
    print(f"   ⚠️  跳過處理: {skipped_channels} 個頻道 (無節目)")
    print(f"   ❌ 處理失敗: {failed_channels} 個頻道")
    print(f"   📁 輸出位置: {output_file}")

if __name__ == "__main__":
    main()
