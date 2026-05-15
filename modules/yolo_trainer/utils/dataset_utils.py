"""
数据集工具模块
==============
- DatasetSplitter: 数据集划分
- DatasetAnalyzer: 数据集分析
- YOLOExporter: 格式导出
"""

import os
import json
import shutil
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter

import cv2
import numpy as np


class DatasetSplitter:
    """数据集划分器"""

    @staticmethod
    def split(image_dir: str, label_dir: str, output_dir: str,
              train_ratio: float = 0.8, val_ratio: float = 0.1,
              test_ratio: float = 0.1, seed: int = 42) -> Dict[str, int]:
        """
        将数据集按比例划分为 train/val/test
        
        Returns:
            {split: count}
        """
        random.seed(seed)
        
        img_dir = Path(image_dir)
        lbl_dir = Path(label_dir)
        out_dir = Path(output_dir)
        
        # 收集有标注的图片
        valid_ext = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        images = []
        for img_path in img_dir.iterdir():
            if img_path.suffix.lower() not in valid_ext:
                continue
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            if lbl_path.exists():
                images.append(img_path)
        
        random.shuffle(images)
        n = len(images)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        
        splits = {
            'train': images[:n_train],
            'val': images[n_train:n_train + n_val],
            'test': images[n_train + n_val:]
        }
        
        stats = {}
        for split_name, split_images in splits.items():
            # 创建目录
            (out_dir / "images" / split_name).mkdir(parents=True, exist_ok=True)
            (out_dir / "labels" / split_name).mkdir(parents=True, exist_ok=True)
            
            for img_path in split_images:
                # 复制图片
                dst_img = out_dir / "images" / split_name / img_path.name
                shutil.copy2(str(img_path), str(dst_img))
                
                # 复制标注
                lbl_path = lbl_dir / f"{img_path.stem}.txt"
                dst_lbl = out_dir / "labels" / split_name / lbl_path.name
                shutil.copy2(str(lbl_path), str(dst_lbl))
            
            stats[split_name] = len(split_images)
        
        return stats

    @staticmethod
    def k_fold_split(image_dir: str, label_dir: str, output_dir: str,
                     k: int = 5, seed: int = 42) -> List[Dict[str, int]]:
        """K 折交叉验证划分"""
        random.seed(seed)
        
        img_dir = Path(image_dir)
        lbl_dir = Path(label_dir)
        
        valid_ext = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        images = [p for p in img_dir.iterdir()
                  if p.suffix.lower() in valid_ext
                  and (lbl_dir / f"{p.stem}.txt").exists()]
        random.shuffle(images)
        
        fold_size = len(images) // k
        folds = []
        
        for i in range(k):
            val_start = i * fold_size
            val_end = val_start + fold_size if i < k - 1 else len(images)
            
            val_images = images[val_start:val_end]
            train_images = images[:val_start] + images[val_end:]
            
            fold_dir = Path(output_dir) / f"fold_{i+1}"
            fold_dir.mkdir(parents=True, exist_ok=True)
            
            for split_name, split_images in [("train", train_images), ("val", val_images)]:
                (fold_dir / "images" / split_name).mkdir(parents=True, exist_ok=True)
                (fold_dir / "labels" / split_name).mkdir(parents=True, exist_ok=True)
                
                for img_path in split_images:
                    shutil.copy2(str(img_path),
                               str(fold_dir / "images" / split_name / img_path.name))
                    lbl_path = lbl_dir / f"{img_path.stem}.txt"
                    shutil.copy2(str(lbl_path),
                               str(fold_dir / "labels" / split_name / lbl_path.name))
            
            folds.append({"fold": i+1, "train": len(train_images), "val": len(val_images)})
        
        return folds


class DatasetAnalyzer:
    """数据集分析器"""

    @staticmethod
    def analyze(image_dir: str, label_dir: str,
                classes: List[str] = None) -> Dict:
        """
        全面分析数据集
        
        Returns:
            分析结果字典
        """
        img_dir = Path(image_dir)
        lbl_dir = Path(label_dir)
        
        total_images = 0
        annotated_images = 0
        total_boxes = 0
        class_counts = Counter()
        box_sizes = []  # 归一化面积
        image_sizes = []
        empty_labels = 0
        
        valid_ext = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        
        for img_path in img_dir.iterdir():
            if img_path.suffix.lower() not in valid_ext:
                continue
            total_images += 1
            
            # 图片尺寸
            img = cv2.imread(str(img_path))
            if img is not None:
                h, w = img.shape[:2]
                image_sizes.append((w, h))
            
            # 标注
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            if not lbl_path.exists():
                continue
            
            with open(lbl_path, 'r') as f:
                lines = f.readlines()
            
            if not lines:
                empty_labels += 1
                continue
            
            annotated_images += 1
            
            for line in lines:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                
                cls_id = int(parts[0])
                bw, bh = float(parts[3]), float(parts[4])
                
                class_counts[cls_id] += 1
                total_boxes += 1
                box_sizes.append(bw * bh)
        
        # 汇总
        result = {
            "total_images": total_images,
            "annotated_images": annotated_images,
            "annotation_coverage": f"{annotated_images/max(1,total_images)*100:.1f}%",
            "total_boxes": total_boxes,
            "empty_label_files": empty_labels,
            "avg_boxes_per_image": total_boxes / max(1, annotated_images),
        }
        
        # 类别分布
        class_dist = {}
        for cls_id, count in sorted(class_counts.items()):
            name = classes[cls_id] if classes and cls_id < len(classes) else f"class_{cls_id}"
            class_dist[name] = {
                "count": count,
                "percentage": f"{count/max(1,total_boxes)*100:.1f}%"
            }
        result["class_distribution"] = class_dist
        
        # 目标尺寸分布
        if box_sizes:
            areas = np.array(box_sizes)
            result["box_size_stats"] = {
                "mean_area": f"{np.mean(areas):.4f}",
                "median_area": f"{np.median(areas):.4f}",
                "small_boxes (<0.01)": int(np.sum(areas < 0.01)),
                "medium_boxes": int(np.sum((areas >= 0.01) & (areas < 0.1))),
                "large_boxes (>=0.1)": int(np.sum(areas >= 0.1)),
            }
        
        # 图片尺寸统计
        if image_sizes:
            widths = [s[0] for s in image_sizes]
            heights = [s[1] for s in image_sizes]
            result["image_size_stats"] = {
                "min": f"{min(widths)}x{min(heights)}",
                "max": f"{max(widths)}x{max(heights)}",
                "mean": f"{int(np.mean(widths))}x{int(np.mean(heights))}",
                "common_sizes": Counter(image_sizes).most_common(5)
            }
        
        return result

    @staticmethod
    def generate_report(image_dir: str, label_dir: str,
                        classes: List[str] = None) -> str:
        """生成文本格式的分析报告"""
        analysis = DatasetAnalyzer.analyze(image_dir, label_dir, classes)
        
        lines = [
            "=" * 50,
            "📊 数据集分析报告",
            "=" * 50,
            f"总图片数: {analysis['total_images']}",
            f"已标注: {analysis['annotated_images']} ({analysis['annotation_coverage']})",
            f"总标注框: {analysis['total_boxes']}",
            f"平均每图框数: {analysis['avg_boxes_per_image']:.1f}",
            "",
            "📋 类别分布:",
        ]
        
        for name, info in analysis.get("class_distribution", {}).items():
            lines.append(f"  {name}: {info['count']} ({info['percentage']})")
        
        if "box_size_stats" in analysis:
            lines.extend(["", "📐 目标尺寸分布:"])
            for k, v in analysis["box_size_stats"].items():
                lines.append(f"  {k}: {v}")
        
        if "image_size_stats" in analysis:
            lines.extend(["", "🖼️ 图片尺寸:"])
            for k, v in analysis["image_size_stats"].items():
                lines.append(f"  {k}: {v}")
        
        lines.append("=" * 50)
        return '\n'.join(lines)


class YOLOExporter:
    """数据集格式导出器"""

    @staticmethod
    def export_coco(image_dir: str, label_dir: str, output_path: str,
                    classes: List[str]) -> str:
        """
        导出为 COCO JSON 格式
        
        Returns:
            输出文件路径
        """
        img_dir = Path(image_dir)
        lbl_dir = Path(label_dir)
        
        coco = {
            "info": {"description": "AutoDoor YOLO Dataset"},
            "licenses": [],
            "images": [],
            "annotations": [],
            "categories": [{"id": i, "name": name} for i, name in enumerate(classes)]
        }
        
        ann_id = 0
        valid_ext = {'.jpg', '.jpeg', '.png', '.bmp'}
        
        for img_id, img_path in enumerate(img_dir.iterdir()):
            if img_path.suffix.lower() not in valid_ext:
                continue
            
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            h, w = img.shape[:2]
            
            coco["images"].append({
                "id": img_id,
                "file_name": img_path.name,
                "width": w,
                "height": h
            })
            
            lbl_path = lbl_dir / f"{img_path.stem}.txt"
            if not lbl_path.exists():
                continue
            
            with open(lbl_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    
                    cls_id = int(parts[0])
                    xc, yc, bw, bh = [float(x) for x in parts[1:5]]
                    
                    # 转换为 COCO 格式 (x, y, w, h) 像素坐标
                    x = (xc - bw / 2) * w
                    y = (yc - bh / 2) * h
                    pw = bw * w
                    ph = bh * h
                    
                    coco["annotations"].append({
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": cls_id,
                        "bbox": [x, y, pw, ph],
                        "area": pw * ph,
                        "iscrowd": 0
                    })
                    ann_id += 1
        
        with open(output_path, 'w') as f:
            json.dump(coco, f, indent=2)
        
        return output_path

    @staticmethod
    def export_yolo(image_dir: str, label_dir: str, output_dir: str,
                    classes: List[str], train_ratio: float = 0.8,
                    val_ratio: float = 0.1):
        """导出标准 YOLO 格式（划分好的数据集）"""
        DatasetSplitter.split(image_dir, label_dir, output_dir,
                             train_ratio, val_ratio, 1 - train_ratio - val_ratio)
        
        # 生成 data.yaml
        out_dir = Path(output_dir)
        yaml_lines = [
            f"path: {out_dir.absolute()}",
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "",
            "names:"
        ]
        for i, name in enumerate(classes):
            yaml_lines.append(f"  {i}: {name}")
        
        with open(out_dir / "data.yaml", 'w') as f:
            f.write('\n'.join(yaml_lines) + '\n')
        
        return str(out_dir)
