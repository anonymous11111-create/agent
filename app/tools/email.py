import logging
from email.message import EmailMessage

import aiosmtplib
from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger(__name__)


@tool
async def send_email(to: str, subject: str, content: str) -> str:
    """发送邮件到指定的收件人。参数包括：to（收件人邮箱地址，必填）、subject（邮件主题，必填）、content（邮件正文内容，必填）。"""
    if not to or not to.strip():
        return "错误：收件人邮箱地址不能为空"
    if not subject or not subject.strip():
        return "错误：邮件主题不能为空"
    if not content or not content.strip():
        return "错误：邮件内容不能为空"
    if "@" not in to:
        return "错误：收件人邮箱地址格式不正确"

    msg = EmailMessage()
    msg["From"] = settings.SMTP_USERNAME
    msg["To"] = to.strip()
    msg["Subject"] = subject.strip()
    msg.set_content(content.strip())

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info("Email sent to %s, subject: %s", to, subject)
        return f"邮件已发送！\n收件人: {to}\n主题: {subject}"
    except Exception as e:
        logger.error("Email failed: %s", e)
        return f"邮件发送失败: {e}"
