import PyPDF2
from io import BytesIO
from fastapi import UploadFile


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