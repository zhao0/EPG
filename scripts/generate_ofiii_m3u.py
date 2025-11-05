import requests
import json
import time
import os
import random
from pathlib import Path
import zipfile

def get_channel_data(channel_id):
    """獲取頻道資料"""
    url = f"https://www.ofiii.com/_next/data/YOQn3leN1n6vChLX_aqzq/channel/watch/{channel_id}.json"
    
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

def create_channel_zip(json_dir, output_dir):
    """將所有頻道JSON檔案壓縮成ZIP"""
    try:
        zip_path = output_dir / "ofiii_channel.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for json_file in json_dir.glob("*.json"):
                zipf.write(json_file, json_file.name)
        
        print(f"✅ 成功建立壓縮檔: {zip_path}")
        return True
    except Exception as e:
        print(f"❌ 建立壓縮檔失敗: {e}")
        return False

def cleanup_json_files(json_dir):
    """清理JSON暫存檔案"""
    try:
        deleted_count = 0
        for json_file in json_dir.glob("*.json"):
            json_file.unlink()
            deleted_count += 1
        
        # 嘗試刪除目錄（如果為空）
        try:
            json_dir.rmdir()
        except OSError:
            pass  # 目錄不為空，不刪除
            
        print(f"🧹 已清理 {deleted_count} 個暫存JSON檔案")
        return deleted_count
    except Exception as e:
        print(f"❌ 清理JSON檔案失敗: {e}")
        return 0

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
            
            # 生成M3U條目 - 使用實際獲取的content_id
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
        content_id = channel_info.get('content_id', channel_id)
        
        return {
            'name': name,
            'picture': f'https://p-cdnstatic.svc.litv.tv/{picture}',
            'group_title': name,
            'content_id': content_id
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

def generate_ofiii_channel_ids(start=13, end=255):
    """動態生成ofiii頻道ID列表"""
    return [f"ofiii{i}" for i in range(start, end + 1)]

def human_delay():
    """模擬人類行為的隨機延遲（3-15秒）"""
    delay_time = random.uniform(3, 15)
    print(f"⏳ 隨機延遲 {delay_time:.1f} 秒...")
    time.sleep(delay_time)

def main():
    # 確保輸出目錄存在
    output_dir = ensure_output_dir()
    json_dir = ensure_json_dir(output_dir)
    m3u_file = output_dir / 'ofiii.m3u'
    channel_json_file = output_dir / 'ofiii_channel.json'
    playout_channel_json_file = output_dir / 'ofiii_playout-channel.json'
    
    # 動態生成ofiii頻道ID列表（13-255）
    ofiii_channels = generate_ofiii_channel_ids(13, 255)
    
    # 頻道ID列表（包含動態生成的ofiii頻道和其他頻道）
    channel_ids = ofiii_channels + [
        # 新增頻道
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
    
    # M3U文件頭
    m3u_content = ['#EXTM3U x-tvg-url=""']
    channel_data = {}
    
    # 用於追蹤已使用的asset_id
    asset_seen = set()
    
    print("🚀 開始獲取頻道資料...")
    print(f"📊 總共 {len(channel_ids)} 個頻道需要處理")
    successful_channels = 0
    failed_channels = 0
    skipped_channels = 0
    total_programs = 0
    total_duplicate_assets = 0
    saved_json_files = 0
    
    # 遍歷所有頻道ID
    for i, channel_id in enumerate(channel_ids, 1):
        print(f"\n📋 處理頻道 {i}/{len(channel_ids)}: {channel_id}")
        
        # 隨機延遲模擬人類行為
        if i > 1:  # 第一個請求不需要延遲
            human_delay()
        
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
                print(f"⚠️ 跳過頻道 {channel_id} (無有效節目)")
        else:
            failed_channels += 1
            print(f"❌ 無法獲取頻道 {channel_id} 資料")
    
    # 去除重複的頻道資料
    print("\n🔄 檢查並移除重複頻道...")
    unique_channel_data = remove_duplicate_channels(channel_data)
    
    # 生成ofiii_playout-channel.json
    print("\n🔄 生成ofiii_playout-channel.json...")
    playout_channel_data = generate_playout_channel_json(channel_ids)
    
    # 寫入M3U文件
    with open(m3u_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(m3u_content))
    
    # 寫入channel.json文件
    with open(channel_json_file, 'w', encoding='utf-8') as f:
        json.dump(unique_channel_data, f, ensure_ascii=False, indent=2)
    
    # 寫入ofiii_playout-channel.json文件
    with open(playout_channel_json_file, 'w', encoding='utf-8') as f:
        json.dump(playout_channel_data, f, ensure_ascii=False, indent=2)
    
    # 建立頻道JSON壓縮檔
    print(f"\n🗜️ 建立頻道JSON壓縮檔...")
    if create_channel_zip(json_dir, output_dir):
        print(f"✅ 成功建立 ofiii_channel.zip，包含 {saved_json_files} 個頻道JSON檔案")
    
    # 清理暫存JSON檔案
    print(f"\n🧹 清理暫存檔案...")
    cleaned_files = cleanup_json_files(json_dir)
    
    print(f"\n🎉 檔案生成完成！")
    print(f"📊 統計資訊:")
    print(f"   ✅ 成功處理: {successful_channels} 個頻道")
    print(f"   ⚠️ 跳過處理: {skipped_channels} 個頻道 (無節目)")
    print(f"   ❌ 處理失敗: {failed_channels} 個頻道")
    print(f"   📺 總節目數: {total_programs} 個節目")
    print(f"   🔄 唯一頻道數: {len(unique_channel_data)} 個頻道")
    print(f"   🔄 跳過重複asset_id: {total_duplicate_assets} 個")
    print(f"   💾 儲存JSON檔案: {saved_json_files} 個")
    print(f"   🧹 清理暫存檔案: {cleaned_files} 個")
    print(f"   📁 輸出檔案:")
    print(f"      - {m3u_file}")
    print(f"      - {channel_json_file}")
    print(f"      - {playout_channel_json_file}")
    print(f"      - {output_dir / 'ofiii_channel.zip'}")

if __name__ == "__main__":
    main()
