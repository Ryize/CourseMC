from PIL import Image, ImageDraw, ImageFont

STATIC_PATH = 'CourseMC/certificate/static'
CERTIFICATES_PATH = f'{STATIC_PATH}/certificates'


def create_certificate(name: str, date: str, certificate_number: str):
    im = Image.open(f'{STATIC_PATH}/certificate.png')
    draw_text = ImageDraw.Draw(im)
    font_fio = ImageFont.truetype(f"{STATIC_PATH}/montserrat.ttf", 90)
    font_date = ImageFont.truetype(f"{STATIC_PATH}/helvetica.ttf", 36)
    font_certificate_number = ImageFont.truetype(
        f"{STATIC_PATH}/helvetica.ttf", 42)

    draw_text.text(
        (200, 680),
        name,
        fill=('#ffffff'),
        font=font_fio
    )

    draw_text.text(
        (282, 1098),
        date,
        fill=('#ffffff'),
        font=font_date
    )

    draw_text.text(
        (995, 1091),
        certificate_number,
        fill=('#ffffff'),
        font=font_certificate_number
    )
    file_path = f'{CERTIFICATES_PATH}/{certificate_number}.png'
    im.save(file_path)
    return file_path
