#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站缓存视频转换工具
将加密的.m4s文件转换为可播放的.mp4文件
"""

import os
import shutil
import subprocess
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VideoConverter:
    def __init__(self, input_dir):
        """
        初始化视频转换器
        
        Args:
            input_dir (str): 包含视频文件夹的根目录
        """
        self.input_dir = Path(input_dir)
        self.output_dir = self.input_dir / "converted_videos"
        
        # 确保输出目录存在
        self.output_dir.mkdir(exist_ok=True)
    
    def remove_encryption_header(self, file_path):
        """
        删除文件开头的9个字节（加密头）
        
        Args:
            file_path (Path): 文件路径
            
        Returns:
            Path: 处理后的临时文件路径
        """
        temp_file = file_path.with_suffix('.temp')
        
        try:
            with open(file_path, 'rb') as input_file:
                # 跳过前9个字节
                input_file.seek(9)
                content = input_file.read()
                
            with open(temp_file, 'wb') as output_file:
                output_file.write(content)
                
            logger.info(f"已处理加密头: {file_path.name}")
            return temp_file
            
        except Exception as e:
            logger.error(f"处理文件 {file_path} 时出错: {e}")
            return None
    def find_m4s_files(self, folder_path):
        """
        在指定文件夹中查找.m4s文件
        
        Args:
            folder_path (Path): 文件夹路径
            
        Returns:
            tuple: (视频文件路径, 音频文件路径) 或 (None, None)
        """
        m4s_files = list(folder_path.glob("*.m4s"))
        
        if len(m4s_files) != 2:
            logger.warning(f"文件夹 {folder_path.name} 中找到 {len(m4s_files)} 个.m4s文件，期望2个")
            return None, None
        
        video_file = None
        audio_file = None
        
        # 根据文件名结尾识别音频和视频文件
        for file in m4s_files:
            file_stem = file.stem  # 文件名（不含扩展名）
            if file_stem.endswith('080'):
                video_file = file
                logger.info(f"识别到视频文件: {file.name} ({file.stat().st_size} bytes)")
            elif file_stem.endswith('280'):
                audio_file = file
                logger.info(f"识别到音频文件: {file.name} ({file.stat().st_size} bytes)")
            else:
                logger.warning(f"未知文件类型: {file.name} (不以080或280结尾)")
        
        if not video_file or not audio_file:
            logger.error(f"无法在文件夹 {folder_path.name} 中找到对应的音频和视频文件")
            logger.error("请确保文件名以080(视频)或280(音频)结尾")
            return None, None
        
        return video_file, audio_file
    
    def merge_video_audio(self, video_file, audio_file, output_file):
        """
        使用ffmpeg合并视频和音频文件
        
        Args:
            video_file (Path): 视频文件路径
            audio_file (Path): 音频文件路径
            output_file (Path): 输出文件路径
            
        Returns:
            bool: 合并是否成功
        """
        try:
            cmd = [
                'ffmpeg',
                '-i', str(video_file),
                '-i', str(audio_file),
                '-c', 'copy',  # 直接复制，不重新编码
                '-y',  # 覆盖输出文件
                str(output_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"成功合并视频: {output_file.name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg合并失败: {e}")
            logger.error(f"错误输出: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("未找到ffmpeg，请确保已安装ffmpeg并添加到PATH环境变量")
            return False
    
    def convert_single_folder(self, folder_path):
        """
        转换单个文件夹中的视频
        
        Args:
            folder_path (Path): 文件夹路径
            
        Returns:
            bool: 转换是否成功
        """
        logger.info(f"处理文件夹: {folder_path.name}")
        
        # 查找.m4s文件
        video_m4s, audio_m4s = self.find_m4s_files(folder_path)
        if not video_m4s or not audio_m4s:
            return False
        
        # 处理视频文件
        video_temp = self.remove_encryption_header(video_m4s)
        if not video_temp:
            return False
        
        # 处理音频文件
        audio_temp = self.remove_encryption_header(audio_m4s)
        if not audio_temp:
            video_temp.unlink()  # 删除临时文件
            return False
        
        # 重命名为.mp4文件
        video_mp4 = video_temp.with_suffix('.mp4')
        audio_mp4 = audio_temp.with_suffix('.mp4')
        
        try:
            video_temp.rename(video_mp4)
            audio_temp.rename(audio_mp4)
        except Exception as e:
            logger.error(f"重命名文件时出错: {e}")
            return False
        
        # 合并视频和音频
        output_file = self.output_dir / f"{folder_path.name}.mp4"
        success = self.merge_video_audio(video_mp4, audio_mp4, output_file)
        
        # 清理临时文件
        try:
            video_mp4.unlink()
            audio_mp4.unlink()
        except Exception as e:
            logger.warning(f"删除临时文件时出错: {e}")
        
        return success
    
    def convert_all(self):
        """
        转换所有文件夹中的视频
        
        Returns:
            int: 成功转换的视频数量
        """
        if not self.input_dir.exists():
            logger.error(f"输入目录不存在: {self.input_dir}")
            return 0
        
        success_count = 0
        total_folders = 0
        
        # 遍历所有子文件夹
        for folder_path in self.input_dir.iterdir():
            if folder_path.is_dir() and folder_path.name != "converted_videos":
                total_folders += 1
                if self.convert_single_folder(folder_path):
                    success_count += 1
                    logger.info(f"✓ 成功转换: {folder_path.name}")
                else:
                    logger.error(f"✗ 转换失败: {folder_path.name}")
        
        logger.info(f"转换完成: {success_count}/{total_folders} 个视频转换成功")
        logger.info(f"输出目录: {self.output_dir}")
        
        return success_count

def main():
    """主函数"""
    # 使用当前脚本所在目录作为输入目录
    current_dir = Path(__file__).parent
    
    print("=== B站缓存视频转换工具 ===")
    print(f"输入目录: {current_dir}")
    print(f"输出目录: {current_dir / 'converted_videos'}")
    print()
    
    # 检查是否有ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✓ 检测到ffmpeg")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠ 警告: 未检测到ffmpeg，请先安装ffmpeg")
        print("下载地址: https://ffmpeg.org/download.html")
        input("按回车键继续...")
    
    # 创建转换器并开始转换
    converter = VideoConverter(current_dir)
    success_count = converter.convert_all()
    
    if success_count > 0:
        print(f"\n🎉 转换完成！成功转换了 {success_count} 个视频")
        print(f"转换后的视频保存在: {converter.output_dir}")
    else:
        print("\n❌ 没有成功转换任何视频，请检查文件格式和目录结构")
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    main()
