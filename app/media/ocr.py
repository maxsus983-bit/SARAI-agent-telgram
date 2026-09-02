from __future__ import annotations

from app.media.vision import analyze_image


async def extract_text_from_image(
    *,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> str:
    """
    Rasm ichidagi yozuvlarni AI vision orqali o'qiydi.
    """

    prompt = """
Bu rasm OCR vazifasi uchun berildi.

Rasm ichidagi barcha ko'rinadigan matnni o'qib ber.

Qoidalar:

1. Matnni imkon qadar aynan yoz.
2. Imlo yoki grammatikani o'zingcha tuzatma.
3. Agar bir nechta matn bo'lsa, ularni alohida qatorlarga ajrat.
4. Matn qaysi tilda bo'lsa, o'sha tilda yoz.
5. O'qib bo'lmaydigan joyni [aniqlanmadi] deb belgila.
6. Agar umuman matn bo'lmasa:
   "Rasmda aniqlanadigan matn yo'q."
   deb yoz.

Faqat OCR natijasini qaytar.
""".strip()

    return await analyze_image(
        image_bytes=image_bytes,
        prompt=prompt,
        mime_type=mime_type,
    )
