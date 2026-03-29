#!/usr/bin/env python3
"""
LingFlow - 教材处理工作流系统

实现大专教材的完整处理流程：
1. 定位教材实体文件路径
2. 提取教材PDF文本
3. 解析教材目录结构
4. 导入教材数据到v2数据库
5. 分割章节验证质量
"""

import json
import logging
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from enum import Enum
from datetime import datetime
import subprocess
import shutil

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepStatus(Enum):
    """步骤状态"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """步骤执行结果"""
    step_name: str
    status: StepStatus
    message: str = ""
    data: Dict = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict:
        return {
            "step_name": self.step_name,
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds
        }


@dataclass
class TextbookInfo:
    """教材信息"""
    number: int                          # 教材编号 1-9
    title: str                           # 教材标题
    short_name: str                      # 简短名称
    pdf_path: Optional[Path] = None      # PDF文件路径
    txt_path: Optional[Path] = None      # TXT文件路径
    docx_path: Optional[Path] = None     # DOCX文件路径
    processed_dir: Optional[Path] = None # 处理后目录
    source_dir: Optional[Path] = None    # 源目录
    quality_score: float = 0.0           # 质量分数
    char_count: int = 0                  # 字符数
    chinese_count: int = 0               # 中文字符数

    def to_dict(self) -> Dict:
        return {
            "number": self.number,
            "title": self.title,
            "short_name": self.short_name,
            "pdf_path": str(self.pdf_path) if self.pdf_path else None,
            "txt_path": str(self.txt_path) if self.txt_path else None,
            "docx_path": str(self.docx_path) if self.docx_path else None,
            "processed_dir": str(self.processed_dir) if self.processed_dir else None,
            "source_dir": str(self.source_dir) if self.source_dir else None,
            "quality_score": self.quality_score,
            "char_count": self.char_count,
            "chinese_count": self.chinese_count
        }


# 9本大专教材定义
TEXTBOOKS = [
    TextbookInfo(
        number=1,
        title="智能气功科学概论",
        short_name="概论"
    ),
    TextbookInfo(
        number=2,
        title="智能气功科学精义",
        short_name="精义"
    ),
    TextbookInfo(
        number=3,
        title="智能气功科学混元整体理论",
        short_name="混元整体理论"
    ),
    TextbookInfo(
        number=4,
        title="智能气功科学功法学",
        short_name="功法学"
    ),
    TextbookInfo(
        number=5,
        title="智能气功科学超常智能",
        short_name="超常智能"
    ),
    TextbookInfo(
        number=6,
        title="智能气功科学传统气功知识综述",
        short_name="传统气功知识综述"
    ),
    TextbookInfo(
        number=7,
        title="智能气功科学气功与人类文化",
        short_name="气功与人类文化"
    ),
    TextbookInfo(
        number=8,
        title="中国气功发展简史",
        short_name="中国气功发展简史"
    ),
    TextbookInfo(
        number=9,
        title="智能气功科学的现代科学研究",
        short_name="气功的现代科学研究"
    ),
]


class LingFlowWorkflow:
    """LingFlow 工作流引擎"""

    def __init__(
        self,
        project_root: Path = None,
        data_dir: Path = None,
        output_dir: Path = None,
        db_path: Path = None
    ):
        """初始化工作流

        Args:
            project_root: 项目根目录
            data_dir: 数据目录
            output_dir: 输出目录
            db_path: 数据库路径
        """
        self.project_root = project_root or Path.cwd()
        self.data_dir = data_dir or self.project_root / "data" / "textbooks"
        self.output_dir = output_dir or self.project_root / "data" / "processed" / "textbooks_v2"
        self.db_path = db_path or self.project_root / "store" / "textbooks_v2.db"

        # 确保目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 工作流状态
        self.steps_results: List[StepResult] = []
        self.textbooks: List[TextbookInfo] = TEXTBOOKS

    def _read_text_with_encoding(self, file_path: Path) -> str:
        """自动检测编码并读取文本

        尝试多种编码格式：utf-8, gbk, gb2312, gb18030
        """
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-16']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                # 验证内容是否合理
                if len(content) > 100 and any('\u4e00' <= c <= '\u9fff' for c in content):
                    logger.debug(f"  使用编码: {encoding}")
                    return content
            except (UnicodeDecodeError, UnicodeError):
                continue

        # 如果所有编码都失败，使用错误处理
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    # ============================================
    # Step 1: 定位教材实体文件路径
    # ============================================

    def step1_locate_files(self) -> StepResult:
        """步骤1: 定位教材实体文件路径"""
        step = "locate_files"
        result = StepResult(step, StepStatus.IN_PROGRESS, started_at=datetime.now())

        try:
            logger.info("开始步骤1: 定位教材文件")

            # 从catalog.json读取已有信息
            catalog_path = self.data_dir / "catalog.json"
            if catalog_path.exists():
                with open(catalog_path, 'r', encoding='utf-8') as f:
                    catalog = json.load(f)

                # 更新教材路径信息
                for textbook in self.textbooks:
                    # 设置处理后目录（无论是否找到文件）
                    dir_name = f"0{textbook.number}-{textbook.short_name}" if textbook.number < 10 else f"{textbook.number}-{textbook.short_name}"
                    textbook.processed_dir = self.output_dir / dir_name

                    # 查找对应的PDF文件
                    pdf_files = self._find_textbook_files(textbook, catalog)
                    if pdf_files:
                        textbook.pdf_path = self.project_root / pdf_files.get('pdf')
                        textbook.txt_path = self.project_root / pdf_files.get('txt') if pdf_files.get('txt') else None
                        textbook.docx_path = self.project_root / pdf_files.get('docx') if pdf_files.get('docx') else None
                        textbook.source_dir = textbook.pdf_path.parent if textbook.pdf_path else None

                result.data = {
                    "textbooks_found": sum(1 for t in self.textbooks if t.pdf_path and t.pdf_path.exists()),
                    "total_textbooks": len(self.textbooks),
                    "details": [t.to_dict() for t in self.textbooks]
                }
                result.message = f"找到 {result.data['textbooks_found']}/{result.data['total_textbooks']} 本教材文件"
                result.status = StepStatus.COMPLETED
            else:
                result.status = StepStatus.FAILED
                result.error = "catalog.json 不存在"

        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            logger.error(f"步骤1失败: {e}")

        result.completed_at = datetime.now()
        self.steps_results.append(result)
        return result

    def _find_textbook_files(self, textbook: TextbookInfo, catalog: Dict) -> Optional[Dict]:
        """在catalog中查找教材文件"""
        files = {'pdf': None, 'txt': None, 'docx': None}

        # 遍历catalog查找匹配的文件
        for category_data in catalog.get('categories', {}).values():
            for file_info in category_data.get('files', []):
                if file_info.get('textbook_number') == textbook.number:
                    ext = file_info.get('extension', '')
                    path = file_info.get('path', '')
                    if ext == 'pdf' and not files['pdf']:
                        files['pdf'] = path
                    elif ext == 'txt' and not files['txt']:
                        files['txt'] = path
                    elif ext == 'docx' and not files['docx']:
                        files['docx'] = path

        return files if files['pdf'] else None

    # ============================================
    # Step 2: 提取教材PDF文本
    # ============================================

    def step2_extract_text(self, force: bool = False) -> StepResult:
        """步骤2: 提取教材PDF文本

        Args:
            force: 是否强制重新提取
        """
        step = "extract_text"
        result = StepResult(step, StepStatus.IN_PROGRESS, started_at=datetime.now())

        try:
            logger.info("开始步骤2: 提取PDF文本")

            extracted_count = 0
            skipped_count = 0
            failed_count = 0

            for textbook in self.textbooks:
                # 检查是否已有文本
                output_file = textbook.processed_dir / "full_text.txt"
                if output_file.exists() and not force:
                    logger.info(f"  {textbook.number}. {textbook.short_name}: 文本已存在，跳过")
                    skipped_count += 1
                    continue

                # 优先使用现有的txt文件
                if textbook.txt_path and textbook.txt_path.exists():
                    logger.info(f"  {textbook.number}. {textbook.short_name}: 使用现有txt文件")
                    textbook.processed_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(textbook.txt_path, output_file)
                    extracted_count += 1
                    continue

                # 从PDF提取
                if textbook.pdf_path and textbook.pdf_path.exists():
                    logger.info(f"  {textbook.number}. {textbook.short_name}: 从PDF提取")
                    success = self._extract_pdf_text(textbook.pdf_path, output_file)
                    if success:
                        extracted_count += 1
                    else:
                        failed_count += 1
                else:
                    logger.warning(f"  {textbook.number}. {textbook.short_name}: 无源文件")
                    failed_count += 1

            result.data = {
                "extracted": extracted_count,
                "skipped": skipped_count,
                "failed": failed_count,
                "total": len(self.textbooks)
            }
            result.message = f"提取: {extracted_count}, 跳过: {skipped_count}, 失败: {failed_count}"
            result.status = StepStatus.COMPLETED if failed_count == 0 else StepStatus.FAILED

        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            logger.error(f"步骤2失败: {e}")

        result.completed_at = datetime.now()
        self.steps_results.append(result)
        return result

    def _extract_pdf_text(self, pdf_path: Path, output_path: Path) -> bool:
        """提取PDF文本

        使用多种方法尝试提取文本。
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 方法1: 尝试使用现有的提取脚本
        script_path = self.project_root / "scripts" / "extract_textbooks_python.py"
        if script_path.exists():
            try:
                result = subprocess.run(
                    ["python3", str(script_path), str(pdf_path), str(output_path)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if output_path.exists() and output_path.stat().st_size > 1000:
                    return True
            except Exception as e:
                logger.debug(f"脚本提取失败: {e}")

        # 方法2: 尝试直接使用pymupdf
        try:
            import pymupdf
            doc = pymupdf.open(str(pdf_path))
            full_text = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                full_text.append(text)

            doc.close()

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(full_text))

            return True
        except ImportError:
            logger.debug("pymupdf未安装")
        except Exception as e:
            logger.debug(f"pymupdf提取失败: {e}")

        # 方法3: 尝试pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(str(pdf_path)) as pdf:
                full_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(full_text))

            return True
        except ImportError:
            logger.debug("pdfplumber未安装")
        except Exception as e:
            logger.debug(f"pdfplumber提取失败: {e}")

        return False

    # ============================================
    # Step 3: 解析教材目录结构
    # ============================================

    def step3_parse_toc(self) -> StepResult:
        """步骤3: 解析教材目录结构"""
        step = "parse_toc"
        result = StepResult(step, StepStatus.IN_PROGRESS, started_at=datetime.now())

        try:
            logger.info("开始步骤3: 解析目录结构")

            # 导入目录解析器
            import sys
            sys.path.insert(0, str(self.project_root / "backend" / "lingflow"))
            from deep_toc_parser import DeepTocParser, ParseMethod

            parsed_count = 0
            toc_data = {}

            for textbook in self.textbooks:
                # 确保processed_dir已初始化
                if textbook.processed_dir is None:
                    dir_name = f"0{textbook.number}-{textbook.short_name}" if textbook.number < 10 else f"{textbook.number}-{textbook.short_name}"
                    textbook.processed_dir = self.output_dir / dir_name

                text_file = textbook.processed_dir / "full_text.txt"
                if not text_file.exists():
                    logger.warning(f"  {textbook.number}. {textbook.short_name}: 文本不存在")
                    continue

                logger.info(f"  {textbook.number}. {textbook.short_name}: 解析目录")

                try:
                    # 自动检测编码
                    content = self._read_text_with_encoding(text_file)

                    parser = DeepTocParser()
                    parse_result = parser.parse(content, ParseMethod.HEURISTIC)

                    # 保存解析结果
                    toc_file = textbook.processed_dir / "toc.json"
                    with open(toc_file, 'w', encoding='utf-8') as f:
                        json.dump(parse_result.to_dict(), f, ensure_ascii=False, indent=2)

                    toc_data[str(textbook.number)] = {
                        "title": textbook.title,
                        "items_count": len(parse_result.items),
                        "confidence": parse_result.confidence,
                        "method": parse_result.parse_method.value,
                        "issues": parse_result.issues
                    }

                    parsed_count += 1
                    logger.info(f"    解析到 {len(parse_result.items)} 个条目，置信度: {parse_result.confidence}")

                except Exception as e:
                    logger.error(f"    解析失败: {e}")
                    toc_data[str(textbook.number)] = {"error": str(e)}

            result.data = {
                "parsed": parsed_count,
                "total": len(self.textbooks),
                "toc_data": toc_data
            }
            result.message = f"解析了 {parsed_count}/{len(self.textbooks)} 本教材目录"
            result.status = StepStatus.COMPLETED

        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            logger.error(f"步骤3失败: {e}")

        result.completed_at = datetime.now()
        self.steps_results.append(result)
        return result

    # ============================================
    # Step 4: 导入教材数据到v2数据库
    # ============================================

    def step4_import_to_db(self) -> StepResult:
        """步骤4: 导入教材数据到v2数据库"""
        step = "import_to_db"
        result = StepResult(step, StepStatus.IN_PROGRESS, started_at=datetime.now())

        try:
            logger.info("开始步骤4: 导入数据库")

            # 使用实际存在的数据库路径
            db_path = self.project_root / "data" / "textbooks.db"
            if not db_path.exists():
                result.data = {"db_exists": False, "db_path": str(db_path)}
                result.message = f"数据库不存在: {db_path}"
                result.status = StepStatus.FAILED
                result.completed_at = datetime.now()
                self.steps_results.append(result)
                return result

            # 导入导入器模块
            import sys
            sys.path.insert(0, str(self.project_root / "backend" / "lingflow"))
            from db_importer import batch_import_textbooks

            # 准备教材信息
            textbooks_data = []
            for textbook in self.textbooks:
                # 确保processed_dir是Path对象
                if textbook.processed_dir is None:
                    dir_name = f"0{textbook.number}-{textbook.short_name}" if textbook.number < 10 else f"{textbook.number}-{textbook.short_name}"
                    textbook.processed_dir = self.output_dir / dir_name

                # 读取质量报告
                quality_file = textbook.processed_dir / "quality_report.json"
                quality_info = {}
                if quality_file.exists():
                    with open(quality_file, 'r', encoding='utf-8') as f:
                        quality_info = json.load(f)

                textbooks_data.append({
                    "number": textbook.number,
                    "short_name": textbook.short_name,
                    "title": textbook.title,
                    "char_count": quality_info.get('char_count', textbook.char_count),
                    "chinese_count": quality_info.get('chinese_count', textbook.chinese_count),
                    "quality_score": quality_info.get('quality_score', textbook.quality_score),
                    "processed_dir": textbook.processed_dir  # 传递Path对象
                })

            # 批量导入
            import_result = batch_import_textbooks(
                db_path=db_path,
                output_dir=self.output_dir,
                textbooks=textbooks_data
            )

            result.data = {
                "db_path": str(db_path),
                "total": import_result["total"],
                "success": import_result["success"],
                "failed": import_result["failed"],
                "details": import_result["details"]
            }
            result.message = f"导入: {import_result['success']}/{import_result['total']} 成功"
            result.status = StepStatus.COMPLETED

        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            logger.error(f"步骤4失败: {e}")

        result.completed_at = datetime.now()
        self.steps_results.append(result)
        return result

    # ============================================
    # Step 5: 分割章节验证质量
    # ============================================

    def step5_split_and_validate(self) -> StepResult:
        """步骤5: 分割章节验证质量"""
        step = "split_and_validate"
        result = StepResult(step, StepStatus.IN_PROGRESS, started_at=datetime.now())

        try:
            logger.info("开始步骤5: 分割章节验证质量")

            # 导入质量验证模块
            import sys
            sys.path.insert(0, str(self.project_root / "scripts"))
            # 这里假设有validate_textbook_quality.py

            validated_count = 0
            quality_reports = {}

            for textbook in self.textbooks:
                # 确保processed_dir已初始化
                if textbook.processed_dir is None:
                    dir_name = f"0{textbook.number}-{textbook.short_name}" if textbook.number < 10 else f"{textbook.number}-{textbook.short_name}"
                    textbook.processed_dir = self.output_dir / dir_name

                text_file = textbook.processed_dir / "full_text.txt"
                toc_file = textbook.processed_dir / "toc.json"

                if not text_file.exists():
                    continue

                logger.info(f"  {textbook.number}. {textbook.short_name}: 验证质量")

                try:
                    # 自动检测编码
                    content = self._read_text_with_encoding(text_file)

                    # 简单质量指标
                    char_count = len(content)
                    chinese_count = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
                    chinese_ratio = chinese_count / char_count if char_count > 0 else 0

                    # 计算内容哈希
                    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

                    # 质量分数 (简单算法)
                    quality_score = 0.0
                    if chinese_ratio > 0.7:
                        quality_score += 30
                    if char_count > 50000:
                        quality_score += 20
                    if char_count > 100000:
                        quality_score += 20
                    if '目录' in content or '第' in content:
                        quality_score += 15
                    if '章' in content or '节' in content:
                        quality_score += 15

                    textbook.char_count = char_count
                    textbook.chinese_count = chinese_count
                    textbook.quality_score = quality_score

                    # 保存质量报告
                    report = {
                        "textbook_number": textbook.number,
                        "title": textbook.title,
                        "char_count": char_count,
                        "chinese_count": chinese_count,
                        "chinese_ratio": round(chinese_ratio, 4),
                        "quality_score": quality_score,
                        "content_hash": content_hash,
                        "has_toc": (textbook.processed_dir / "toc.json").exists(),
                        "validated_at": datetime.now().isoformat()
                    }

                    report_file = textbook.processed_dir / "quality_report.json"
                    with open(report_file, 'w', encoding='utf-8') as f:
                        json.dump(report, f, ensure_ascii=False, indent=2)

                    quality_reports[str(textbook.number)] = report
                    validated_count += 1

                    logger.info(f"    质量: {quality_score:.1f}/100, 字符: {char_count:,}")

                except Exception as e:
                    logger.error(f"    验证失败: {e}")
                    quality_reports[str(textbook.number)] = {"error": str(e)}

            result.data = {
                "validated": validated_count,
                "total": len(self.textbooks),
                "reports": quality_reports
            }
            result.message = f"验证了 {validated_count}/{len(self.textbooks)} 本教材"
            result.status = StepStatus.COMPLETED

        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            logger.error(f"步骤5失败: {e}")

        result.completed_at = datetime.now()
        self.steps_results.append(result)
        return result

    # ============================================
    # 工作流执行
    # ============================================

    def run(
        self,
        steps: Optional[List[int]] = None,
        force_extract: bool = False
    ) -> Dict:
        """运行工作流

        Args:
            steps: 要执行的步骤列表 [1,2,3,4,5]，None表示执行全部
            force_extract: 是否强制重新提取文本

        Returns:
            执行结果摘要
        """
        if steps is None:
            steps = [1, 2, 3, 4, 5]

        logger.info(f"LingFlow 工作流开始 - 步骤: {steps}")

        step_methods = {
            1: self.step1_locate_files,
            2: lambda: self.step2_extract_text(force=force_extract),
            3: self.step3_parse_toc,
            4: self.step4_import_to_db,
            5: self.step5_split_and_validate
        }

        for step_num in steps:
            if step_num in step_methods:
                result = step_methods[step_num]()
                if result.status == StepStatus.FAILED:
                    logger.warning(f"步骤{step_num}失败，但继续执行后续步骤")

        # 生成工作流报告
        return self.generate_report()

    def generate_report(self) -> Dict:
        """生成工作流执行报告"""
        completed = sum(1 for r in self.steps_results if r.status == StepStatus.COMPLETED)
        failed = sum(1 for r in self.steps_results if r.status == StepStatus.FAILED)

        report = {
            "workflow": "LingFlow 教材处理工作流",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_steps": len(self.steps_results),
                "completed": completed,
                "failed": failed,
                "success_rate": f"{completed / len(self.steps_results) * 100:.1f}%" if self.steps_results else "N/A"
            },
            "steps": [r.to_dict() for r in self.steps_results],
            "textbooks": [t.to_dict() for t in self.textbooks]
        }

        # 保存报告
        report_path = self.output_dir / "workflow_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"工作流报告已保存: {report_path}")
        return report


# ============================================
# 便捷函数
# ============================================

def run_workflow(
    project_root: Optional[Path] = None,
    steps: Optional[List[int]] = None,
    force_extract: bool = False
) -> Dict:
    """运行LingFlow工作流

    Args:
        project_root: 项目根目录
        steps: 要执行的步骤列表
        force_extract: 是否强制重新提取文本

    Returns:
        执行结果摘要
    """
    if project_root is None:
        # 自动检测项目根目录
        current = Path.cwd()
        # 从当前目录向上查找，直到找到真正的项目根目录
        # 项目根目录应该包含 data/textbooks 目录
        while current != current.parent:
            # 检查是否包含完整的项目结构
            has_data = (current / "data" / "processed" / "textbooks_v2").exists()
            has_backend = (current / "backend" / "lingflow").exists()
            has_frontend = (current / "frontend").exists()

            if has_data and (has_backend or has_frontend):
                project_root = current
                break
            current = current.parent
        else:
            # 如果找不到，使用当前目录的父目录
            project_root = Path.cwd().parent if (Path.cwd() / "backend").exists() else Path.cwd()

    workflow = LingFlowWorkflow(project_root=project_root)
    return workflow.run(steps=steps, force_extract=force_extract)


if __name__ == "__main__":
    import sys

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 解析命令行参数
    steps_arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if steps_arg == "all":
        steps = None
    else:
        steps = [int(s) for s in steps_arg.split(",")]

    # 运行工作流
    result = run_workflow(steps=steps)

    # 打印摘要
    print("\n" + "="*60)
    print("LingFlow 工作流执行完成")
    print("="*60)
    print(f"完成步骤: {result['summary']['completed']}/{result['summary']['total_steps']}")
    print(f"成功率: {result['summary']['success_rate']}")
    print("\n步骤详情:")
    for step in result['steps']:
        status_icon = "✓" if step['status'] == "completed" else "✗"
        print(f"  {status_icon} {step['step_name']}: {step['status']}")
        if step['message']:
            print(f"      {step['message']}")
