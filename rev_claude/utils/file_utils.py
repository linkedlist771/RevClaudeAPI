from docx import Document
from fastapi import UploadFile
from pydantic import BaseModel
from starlette.datastructures import UploadFile as StarletteUploadFile
from pdfminer.high_level import extract_text_to_fp
from io import BytesIO, StringIO
from pdfminer.layout import LAParams
import asyncio
from loguru import logger

from rev_claude.utils.async_task_utils import submit_task2event_loop


class DocumentConvertedResponse(BaseModel):
    file_name: str
    file_type: str
    file_size: int
    extracted_content: str


class DocumentConverter:

    def __init__(self, upload_file: UploadFile):
        self.upload_file = upload_file

    async def convert(self):
        file_name = self.upload_file.filename
        file_type = self.upload_file.content_type
        content = await self.upload_file.read()
        file_size = len(content)
        logger.debug(f"file_type: {file_type}")
        if self.is_text_file():
            extracted_content = await self.process_text(content)
            return DocumentConvertedResponse(
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                extracted_content=extracted_content,
            )
        # docx, pdf,
        elif self.is_pdf_file():
            extracted_content = await self.process_pdf(content)
            return DocumentConvertedResponse(
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                extracted_content=extracted_content,
            )

        elif self.is_docx_file():
            extracted_content = await self.process_docx(content)
            return DocumentConvertedResponse(
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                extracted_content=extracted_content,
            )

        else:
            return None

    def is_text_file(self):
        # 检查内容类型是否为文本类型
        text_types = [
            "text/plain",  # 普通文本
            "text/csv",  # CSV 文件
            "text/html",  # HTML 文档
            "application/json",  # JSON 数据
            "text/xml",  # XML 文档
            "application/octet-stream",  # 通用二进制流（可能需要进一步处理来确定类型）
            "text/yaml",  # YAML 文件
            "application/xml",  # XML 文件（通常用于网络服务）
            "text/markdown",  # Markdown 文本
            "text/css",  # CSS 文件
            "application/javascript",  # JavaScript 代码
            "application/x-javascript",  # 也是 JavaScript 代码
            "text/javascript",  # 过时的 JavaScript MIME 类型
            "application/x-yaml",  # 另一种 YAML 类型标识
            "application/x-latex",  # LaTeX 文档
            "application/x-tex",  # TeX 文档
            "text/sgml",  # SGML 文档
            "application/sgml",  # SGML 应用程序类型
        ]

        bool_in_list = self.upload_file.content_type in text_types
        bool_start_with_txt = self.upload_file.content_type.startswith("text")

        return bool_in_list or bool_start_with_txt

    def is_pdf_file(self):
        # 检查文件是否为PDF
        return self.upload_file.content_type == "application/pdf"

    def is_docx_file(self):
        # 检查文件是否为DOCX
        return (
            self.upload_file.content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def process_text_sync(self, content):
        # 处理文本文件
        return content.decode("utf-8")

    async def process_text(self, content):
        # 使用 run_in_threadpool 处理同步操作
        extracted_text = await submit_task2event_loop(self.process_text_sync, content)
        return extracted_text

    def process_pdf_sync(self, content):
        # 将二进制内容转换为类文件对象
        pdf_content = BytesIO(content)

        # 准备一个输出缓冲区来捕获文本
        output_buffer = StringIO()

        # 调用函数
        extract_text_to_fp(
            inf=pdf_content, outfp=output_buffer, codec="utf-8", laparams=LAParams()
        )

        # 从输出缓冲区中检索提取的文本
        extracted_text = output_buffer.getvalue()
        return extracted_text

    async def process_pdf(self, content):
        # 使用 run_in_threadpool 处理同步操作
        extracted_text = await submit_task2event_loop(self.process_pdf_sync, content)
        return extracted_text

    def process_docx_sync(self, content):
        # Convert the binary content to a file-like object
        docx_file = BytesIO(content)

        # Load the DOCX file with python-docx
        doc = Document(docx_file)

        # Extract text from each paragraph in the document
        extracted_text = "\n".join(
            paragraph.text for paragraph in doc.paragraphs if paragraph.text
        )

        # Optionally, handle more complex structures like tables, headers, footers if needed
        # For simplicity, this example focuses only on text in paragraphs

        return extracted_text

    async def process_docx(self, content):
        extracted_text = await submit_task2event_loop(self.process_docx_sync, content)

        return extracted_text


async def main():
    files_list = [
        "example.txt",
        "example.csv",
        "example.json",
        "AI-agent.pdf",
        "Sample_Document.docx",
    ]
    files_list = [f"resources/{file}" for file in files_list]
    files_type = [
        "text/plain",
        "text/csv",
        "application/json",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    file_content_list = [open(file_path, "rb").read() for file_path in files_list]

    upload_file_list = [
        StarletteUploadFile(
            filename=file_path,
            file=BytesIO(file_content),
            headers={"content-type": file_type},
        )
        for file_path, file_content, file_type in zip(
            files_list, file_content_list, files_type
        )
    ]

    # 初始化 DocumentConverter
    converter_list = [
        DocumentConverter(upload_file) for upload_file in upload_file_list
    ]

    for converter in converter_list:
        result = await converter.convert()
        # 处理转换后的结果，例如保存或打印
        print(result)


# 运行主函数
if __name__ == "__main__":
    asyncio.run(main())
