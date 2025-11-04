import requests
import json
import time
import os
from pathlib import Path
import gzip
import tarfile

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

def save_channel_json(channel_id, channel_data, json_dir):
    """將頻道JSON資料儲存為檔案"""
    try:
        json_file = json_dir / f"{channel_id}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(channel_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ 儲存頻道 {channel_id} JSON檔案失敗: {e}")
        return False

def create_channel_gz(json_dir, output_dir):
    """將所有頻道JSON檔案壓縮成GZ"""
    try:
        # 创建tar.gz文件
        gz_path = output_dir / "ofiii_channel.tar.gz"
        
        with tarfile.open(gz_path, 'w:gz') as tar:
            for json_file in json_dir.glob("*.json"):
                tar.add(json_file, arcname=json_file.name)
        
        print(f"✅ 成功建立GZ壓縮檔: {gz_path}")
        return True
    except Exception as e:
        print(f"❌ 建立GZ壓縮檔失敗: {e}")
        return False

def get_display_name(title, subtitle):
    """根據標題和副標題生成顯示名稱"""
    if title and subtitle:
        return f"{title}-{subtitle}"
    elif title and not subtitle:
        return title
    elif not title and subtitle:
        return subtitle
    else:
        return "未知節目"

def generate_m3u_content(channel_data, channel_id, asset_seen):
    """生成M3U內容，並去除重複的asset_id"""
    m3u_lines = []
    added_programs = 0
    duplicate_assets = 0
    
    try:
        page_props = channel_data.get('pageProps', {})
        channel_info = page_props.get('channel', {})
        
        if not channel_info:
            print(f"⚠️  頻道 {channel_id} 沒有channel資訊")
            return m3u_lines, added_programs, duplicate_assets
        
        # 基本頻道資訊
        name = channel_info.get('title', 'Unknown')
        picture = channel_info.get('picture', '')
        content_id = channel_info.get('content_id', channel_id)
        
        # 獲取節目列表
        schedule = channel_info.get('vod_channel_schedule', {})
        programs = schedule.get('programs', [])
        
        if not programs:
            print(f"ℹ️  頻道 {name} 沒有節目列表，跳過")
            return m3u_lines, added_programs, duplicate_assets
        
        print(f"📺 處理頻道: {name} ({channel_id}) - 找到 {len(programs)} 個節目")
        
        for program in programs:
            asset_id = program.get('asset_id', '')
            title = program.get('title', '')
            subtitle = program.get('subtitle', '')
            
            if not asset_id:
                continue
                
            # 檢查asset_id是否已經存在
            if asset_id in asset_seen:
                duplicate_assets += 1
                continue
                
            # 標記asset_id為已使用
            asset_seen.add(asset_id)
                
            # 生成顯示名稱
            display_name = get_display_name(title, subtitle)
            
            # 生成M3U條目
            extinf_line = f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" tvg-logo="https://p-cdnstatic.svc.litv.tv/{picture}" group-title="{name}",{display_name}'
            url_line = f'http://localhost:5050/play/{content_id}/index.m3u8?episode_id={asset_id}'
            
            m3u_lines.append(extinf_line)
            m3u_lines.append(url_line)
            added_programs += 1
            
    except Exception as e:
        print(f"❌ 處理頻道 {channel_id} 資料時發生錯誤: {e}")
    
    return m3u_lines, added_programs, duplicate_assets

def get_channel_info(channel_data, channel_id):
    """獲取頻道基本資訊"""
    try:
        page_props = channel_data.get('pageProps', {})
        channel_info = page_props.get('channel', {})
        
        if not channel_info:
            return None
        
        name = channel_info.get('title', 'Unknown')
        picture = channel_info.get('picture', '')
        
        return {
            'name': name,
            'picture': f'https://p-cdnstatic.svc.litv.tv/{picture}',
            'group_title': name
        }
    except Exception as e:
        print(f"❌ 獲取頻道 {channel_id} 資訊時發生錯誤: {e}")
        return None

def ensure_output_dir():
    """確保輸出目錄存在"""
    output_dir = Path('../output')
    output_dir.mkdir(exist_ok=True)
    return output_dir

def ensure_json_dir(output_dir):
    """確保JSON暫存目錄存在"""
    json_dir = output_dir / 'channel_json'
    json_dir.mkdir(exist_ok=True)
    return json_dir

def remove_duplicate_channels(channel_data):
    """去除重複的頻道資料"""
    unique_channels = {}
    duplicates_removed = 0
    
    for channel_id, channel_info in channel_data.items():
        # 使用頻道名稱作為唯一標識
        channel_name = channel_info[0]
        
        # 如果這個頻道名稱還不存在，則添加
        if channel_name not in unique_channels:
            unique_channels[channel_name] = (channel_id, channel_info)
        else:
            # 如果已經存在，保留第一個找到的，移除重複的
            duplicates_removed += 1
            print(f"🔄 移除重複頻道: {channel_name} (ID: {channel_id})")
    
    # 重建不重複的頻道字典
    result = {channel_id: channel_info for channel_id, channel_info in unique_channels.values()}
    
    if duplicates_removed > 0:
        print(f"🔄 總共移除了 {duplicates_removed} 個重複頻道")
    
    return result

def generate_playout_channel_json(channel_ids):
    """生成ofiii_playout-channel.json檔案"""
    playout_data = {}
    
    for channel_id in channel_ids:
        playout_data[channel_id] = ["ofiii", channel_id]
    
    return playout_data

def main():
    # 確保輸出目錄存在
    output_dir = ensure_output_dir()
    json_dir = ensure_json_dir(output_dir)
    m3u_file = output_dir / 'ofiii.m3u'
    channel_json_file = output_dir / 'ofiii_channel.json'
    playout_channel_json_file = output_dir / 'ofiii_playout-channel.json'
    
    # 頻道ID列表（包含新增頻道）
    channel_ids = [
        "ofiii13","ofiii16","ofiii22","ofiii23","ofiii24","ofiii31","ofiii32",
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
        "ofiii252","ofiii254","ofiii255",
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
        "daystar"
    ]
    
    # M3U檔案頭
    m3u_content = ['#EXTM3U x-tvg-url=""']
    channel_data = {}
    
    # 用於追蹤已使用的asset_id
    asset_seen = set()
    
    print("🚀 開始獲取頻道資料...")
    successful_channels = 0
    failed_channels = 0
    skipped_channels = 0
    total_programs = 0
    total_duplicate_assets = 0
    saved_json_files = 0
    
    # 遍歷所有頻道ID
    for i, channel_id in enumerate(channel_ids, 1):
        print(f"\n📋 處理頻道 {i}/{len(channel_ids)}: {channel_id}")
        
        # 獲取頻道資料
        channel_json = get_channel_data(channel_id)
        
        if channel_json:
            # 儲存頻道JSON資料
            if save_channel_json(channel_id, channel_json, json_dir):
                saved_json_files += 1
                print(f"💾 已儲存 {channel_id}.json")
            
            # 獲取頻道基本資訊
            channel_info = get_channel_info(channel_json, channel_id)
            
            if channel_info:
                # 添加到channel.json資料
                channel_data[channel_id] = [
                    channel_info['name'],
                    channel_info['picture'],
                    channel_info['group_title']
                ]
            
            # 生成M3U內容
            channel_lines, added_programs, duplicate_assets = generate_m3u_content(channel_json, channel_id, asset_seen)
            total_duplicate_assets += duplicate_assets
            
            if channel_lines:
                m3u_content.extend(channel_lines)
                successful_channels += 1
                total_programs += added_programs
                
                if duplicate_assets > 0:
                    print(f"✅ 成功添加頻道 {channel_id} ({added_programs} 個節目, 跳過 {duplicate_assets} 個重複asset_id)")
                else:
                    print(f"✅ 成功添加頻道 {channel_id} ({added_programs} 個節目)")
            else:
                skipped_channels += 1
        else:
            failed_channels += 1
        
        # 添加延遲避免請求過快
        time.sleep(0.5)
    
    # 去除重複的頻道資料
    print("\n🔄 檢查並移除重複頻道...")
    unique_channel_data = remove_duplicate_channels(channel_data)
    
    # 生成ofiii_playout-channel.json
    print("\n🔄 生成ofiii_playout-channel.json...")
    playout_channel_data = generate_playout_channel_json(channel_ids)
    
    # 寫入M3U檔案
    with open(m3u_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_content))
    
    # 寫入channel.json檔案
    with open(channel_json_file, 'w', encoding='utf-8') as f:
        json.dump(unique_channel_data, f, ensure_ascii=False, indent=2)
    
    # 寫入ofiii_playout-channel.json檔案
    with open(playout_channel_json_file, 'w', encoding='utf-8') as f:
        json.dump(playout_channel_data, f, ensure_ascii=False, indent=2)
    
    # 建立頻道JSON壓縮檔
    print(f"\n🗜️ 建立頻道JSON GZ壓縮檔...")
    if create_channel_gz(json_dir, output_dir):
        print(f"✅ 成功建立 ofiii_channel.tar.gz，包含 {saved_json_files} 個頻道JSON檔案")
    
    print(f"\n🎉 檔案生成完成！")
    print(f"📊 統計資訊:")
    print(f"   ✅ 成功處理: {successful_channels} 個頻道")
    print(f"   ⚠️  跳過處理: {skipped_channels} 個頻道 (無節目)")
    print(f"   ❌ 處理失敗: {failed_channels} 個頻道")
    print(f"   📺 總節目數: {total_programs} 個節目")
    print(f"   🔄 唯一頻道數: {len(unique_channel_data)} 個頻道")
    print(f"   🔄 跳過重複asset_id: {total_duplicate_assets} 個")
    print(f"   💾 儲存JSON檔案: {saved_json_files} 個")
    print(f"   📁 輸出檔案:")
    print(f"      - {m3u_file}")
    print(f"      - {channel_json_file}")
    print(f"      - {playout_channel_json_file}")
    print(f"      - {output_dir / 'ofiii_channel.tar.gz'}")

if __name__ == "__main__":
    main()
