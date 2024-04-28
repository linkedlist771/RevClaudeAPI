from docx import Document
from fastapi import UploadFile
from pydantic import BaseModel
from starlette.datastructures import UploadFile as StarletteUploadFile
from pdfminer.high_level import extract_text_to_fp
from io import BytesIO, StringIO
from pdfminer.layout import LAParams
import asyncio


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
            "text/plain",
            "text/csv",
            "text/html",
            "application/json",
            "text/xml",
        ]
        return self.upload_file.content_type in text_types

    def is_pdf_file(self):
        # 检查文件是否为PDF
        return self.upload_file.content_type == "application/pdf"

    def is_docx_file(self):
        # 检查文件是否为DOCX
        return (
            self.upload_file.content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    async def process_text(self, content):
        # 处理文本文件
        return content.decode("utf-8")

    async def process_pdf(self, content):
        # Use run_in_threadpool to handle synchronous pdfplumber operations
        # Assuming 'content' is the PDF data read from a file-like object
        pdf_content = BytesIO(content)  # Since content is already read as bytes

        # Prepare an output buffer to capture the text
        output_buffer = StringIO()

        # Call the function
        extract_text_to_fp(
            inf=pdf_content, outfp=output_buffer, codec="utf-8", laparams=LAParams()
        )

        # Retrieve the extracted text from the output buffer
        extracted_text = output_buffer.getvalue()
        return extracted_text

    async def process_docx(self, content):
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
