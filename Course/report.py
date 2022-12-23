def get_content_disposition():
    return 'attachment; filename=programCoursePython.docx'


def get_content_type():
    vnd_format = 'vnd.openxmlformats-officedocument.wordprocessingml.document'
    return 'application/{vnd_format}'.format(vnd_format=vnd_format)
