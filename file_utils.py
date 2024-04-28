import PyPDF2
from io import BytesIO
from fastapi import UploadFile
import asyncio
from pydantic import BaseModel
from io import BytesIO
from starlette.datastructures import UploadFile as StarletteUploadFile




async def process_pdf(file: UploadFile):
    # return JSONResponse(content={
    #     "file_name": file.filename,
    #     "file_type": file.content_type,
    #     "file_size": file_size,
    #     "extracted_content": file_contents.decode("utf-8")  # 假设文件编码为 UTF-8
    # })
    file_name = file.filename
    file_type = file.content_type
    content = await file.read()
    file_size = len(content)
    pdf_bytes = BytesIO(content)
    pdf_document = PyPDF2.PdfFileReader(pdf_bytes)
    num_pages = pdf_document.getNumPages()
    text = []
    for page_num in range(num_pages):
        page = pdf_document.getPage(page_num)
        text.append(page.extract_text())
    text = "\n".join(text)
    return {
        "file_name": file_name,
        "file_type": file_type,
        "file_size": file_size,
        "extracted_content": text,
    }


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

        if self.is_text_file():
            extracted_content = await self.process_text(content)
            return DocumentConvertedResponse(file_name=file_name,
                                                file_type=file_type,
                                                file_size=file_size,
                                                extracted_content=extracted_content)
        # docx, pdf,

        else:
            return None

    def is_text_file(self):
        # 检查内容类型是否为文本类型
        text_types = ["text/plain", "text/csv", "text/html", "application/json", "text/xml"]
        return self.upload_file.content_type in text_types

    def is_pdf_file(self):
        # 检查文件是否为PDF
        return self.upload_file.content_type == "application/pdf"

    def is_docx_file(self):
        # 检查文件是否为DOCX
        return self.upload_file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    async def process_text(self, content):
        # 处理文本文件
        return content.decode("utf-8")

    async def process_pdf(self, content):
        raise NotImplementedError

    async def process_docx(self, content):
        raise NotImplementedError





# 本地文件路径
file_path = 'example.txt'  # 更改为你的文件路径
file_content = open(file_path, 'rb').read()

# 创建 UploadFile 对象
upload_file = StarletteUploadFile(filename='example.txt',
                                  content_type='text/plain',
                                  file=BytesIO(file_content))

# 初始化 DocumentConverter
converter = DocumentConverter(upload_file)

# 使用 asyncio 运行转换方法
import asyncio

async def main():
    result = await converter.convert()
    # 处理转换后的结果，例如保存或打印
    print(result.getvalue())

# 运行主函数
if __name__ == "__main__":
    asyncio.run(main())