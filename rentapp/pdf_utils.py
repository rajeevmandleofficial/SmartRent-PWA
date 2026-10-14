import io
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa


def render_to_pdf(template_src, context_dict={}):
    """
    Renders a Django template to a PDF document using xhtml2pdf.
    Returns an HttpResponse with PDF attachment or inline stream.
    """
    template = get_template(template_src)
    html = template.render(context_dict)
    result = io.BytesIO()
    
    # Generate PDF
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result, encoding='UTF-8')
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None
