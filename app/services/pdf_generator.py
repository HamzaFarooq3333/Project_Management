from io import BytesIO
from typing import Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


def _para(text: str) -> Paragraph:
    styles = getSampleStyleSheet()
    return Paragraph(text.replace('\n', '<br/>'), styles['BodyText'])


def _h(text: str, level: int = 2) -> Paragraph:
    styles = getSampleStyleSheet()
    style = styles['Heading2'] if level == 2 else styles['Heading3']
    return Paragraph(text, style)


def _build_citations_table(citations: List[Dict[str, Any]]) -> Table:
    data = [["Standard", "Page", "Excerpt"]]
    for c in citations[:30]:
        data.append([
            str(c.get('standard', '')),
            str(c.get('page', '')),
            (c.get('excerpt', '') or '')[:160]
        ])
    tbl = Table(data, colWidths=[4*cm, 2*cm, 10*cm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#32406f')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    return tbl


def generate_process_pdf(data: Dict[str, Any]) -> bytes:
    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=A4, title="Process Recommendation")
    story: List[Any] = []

    title = f"Process Recommendation — {data.get('project_size','?').title()} {data.get('project_type','?').title()} ({data.get('industry','?')})"
    story.append(_h(title, level=2))
    story.append(Spacer(1, 0.3*cm))

    scenario = data.get('scenario_description') or ''
    if scenario:
        story.append(_para(f"<b>Scenario:</b> {scenario}"))
        story.append(Spacer(1, 0.2*cm))

    process_text = data.get('process_text') or ''
    story.append(_h('Process Outline', level=3))
    story.append(_para(process_text))
    story.append(Spacer(1, 0.4*cm))

    # Roles
    roles = data.get('roles') or []
    if roles:
        story.append(_h('Roles', level=3))
        story.append(_para(", ".join([str(r) for r in roles])))
        story.append(Spacer(1, 0.4*cm))

    # RACI (flatten)
    raci = data.get('raci') or {}
    if isinstance(raci, dict) and raci:
        story.append(_h('RACI Matrix', level=3))
        rows = [["Activity", "Assignments"]]
        for act_id, entries in raci.items():
            txt = ", ".join([f"{e.get('role')}: {e.get('assignment')}" for e in entries])
            rows.append([act_id, txt])
        tbl = Table(rows, colWidths=[6*cm, 10*cm])
        tbl.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.4*cm))

    # Decision Gates
    gates = data.get('decision_gates') or []
    if isinstance(gates, list) and gates:
        story.append(_h('Decision Gates', level=3))
        for g in gates:
            story.append(_para(f"<b>{g.get('name','Gate')}</b>: Entry: {', '.join(g.get('entry',[]))} | Exit: {', '.join(g.get('exit',[]))}"))
        story.append(Spacer(1, 0.4*cm))

    # Citations
    citations = data.get('citations') or []
    if citations:
        story.append(_h('Citations', level=3))
        story.append(_build_citations_table(citations))
        story.append(Spacer(1, 0.4*cm))

    # Evidence
    if data.get('evidence_base'):
        story.append(_h('Evidence Base', level=3))
        story.append(_para(str(data['evidence_base'])))
        story.append(Spacer(1, 0.4*cm))

    doc.build(story)
    return buff.getvalue()

"""
PDF Document Generation Service
Generates professional PDF documents for process recommendations
"""

import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, darkblue, darkred
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib import colors


class PDFGenerator:
    """Generate professional PDF documents for process recommendations"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for the PDF"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            textColor=HexColor('#e94560'),
            alignment=TA_CENTER
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=16,
            textColor=HexColor('#32406f'),
            alignment=TA_LEFT
        ))
        
        # Process step style
        self.styles.add(ParagraphStyle(
            name='ProcessStep',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            leftIndent=20,
            textColor=black
        ))
        
        # Citation style
        self.styles.add(ParagraphStyle(
            name='Citation',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceAfter=6,
            leftIndent=30,
            textColor=HexColor('#666666'),
            fontName='Helvetica-Oblique'
        ))
        
        # Justification style
        self.styles.add(ParagraphStyle(
            name='Justification',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=12,
            leftIndent=20,
            textColor=HexColor('#444444'),
            alignment=TA_JUSTIFY
        ))

    def generate_process_document(
        self, 
        process_data: Dict[str, Any],
        output_path: str = None
    ) -> bytes:
        """
        Generate a comprehensive PDF document for process recommendations
        
        Args:
            process_data: Dictionary containing process information
            output_path: Optional path to save the PDF file
            
        Returns:
            bytes: PDF document as bytes
        """
        # Create in-memory buffer
        buffer = io.BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Build document content
        story = []
        
        # Add title page
        story.extend(self._create_title_page(process_data))
        story.append(PageBreak())
        
        # Add process overview
        story.extend(self._create_process_overview(process_data))
        story.append(PageBreak())
        
        # Add detailed process steps
        story.extend(self._create_process_steps(process_data))
        
        # Add citations and references
        if process_data.get('citations'):
            story.append(PageBreak())
            story.extend(self._create_citations_section(process_data))
        
        # Add justification section
        if process_data.get('justification'):
            story.append(PageBreak())
            story.extend(self._create_justification_section(process_data))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        # Save to file if path provided
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return pdf_bytes

    def _create_title_page(self, process_data: Dict[str, Any]) -> List:
        """Create the title page of the document"""
        elements = []
        
        # Main title
        title = f"Process Recommendation Document"
        elements.append(Paragraph(title, self.styles['CustomTitle']))
        elements.append(Spacer(1, 20))
        
        # Project information table
        project_info = [
            ['Project Type:', process_data.get('project_type', 'N/A')],
            ['Project Size:', process_data.get('project_size', 'N/A')],
            ['Industry:', process_data.get('industry', 'N/A')],
            ['Methodology:', process_data.get('methodology_preference', 'N/A')],
            ['Generated On:', datetime.now().strftime('%B %d, %Y at %I:%M %p')],
        ]
        
        table = Table(project_info, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#dee2e6'))
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 30))
        
        # Description
        if process_data.get('scenario_description'):
            elements.append(Paragraph("Project Context", self.styles['SectionHeader']))
            elements.append(Paragraph(process_data['scenario_description'], self.styles['Normal']))
        
        return elements

    def _create_process_overview(self, process_data: Dict[str, Any]) -> List:
        """Create the process overview section"""
        elements = []
        
        elements.append(Paragraph("Process Overview", self.styles['SectionHeader']))
        elements.append(Spacer(1, 12))
        
        # Process summary
        if process_data.get('process_text'):
            # Enhanced process analysis
            process_text = process_data['process_text']
            lines = [line.strip() for line in process_text.split('\n') if line.strip()]
            
            # Count different types of content
            steps = [line for line in lines if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')) or 
                    line.startswith(('1)', '2)', '3)', '4)', '5)', '6)', '7)', '8)', '9)'))]
            
            phases = [line for line in lines if any(keyword in line.lower() for keyword in ['phase', 'stage', 'initiation', 'planning', 'execution', 'monitoring', 'closing'])]
            
            activities = [line for line in lines if any(keyword in line.lower() for keyword in ['activity', 'task', 'action', 'deliverable'])]
            
            elements.append(Paragraph(f"This comprehensive process contains {len(steps)} detailed steps, {len(phases)} phases, and {len(activities)} activities designed specifically for a {process_data.get('project_size', 'N/A')} {process_data.get('project_type', 'N/A')} project in the {process_data.get('industry', 'N/A')} industry.", self.styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # Add process methodology info
            methodology = process_data.get('methodology_preference', 'N/A')
            elements.append(Paragraph(f"Methodology: {methodology}", self.styles['Normal']))
            elements.append(Spacer(1, 8))
            
            elements.append(Paragraph("The process is based on evidence from the following standards:", self.styles['Normal']))
            
            # Standards used
            if process_data.get('citations'):
                standards = set()
                for citation in process_data['citations'].get('used_references', []):
                    standards.add(citation.get('standard', 'Unknown'))
                
                for standard in sorted(standards):
                    elements.append(Paragraph(f"• {standard}", self.styles['Normal']))
            else:
                elements.append(Paragraph(f"• {methodology} standards", self.styles['Normal']))
        
        return elements

    def _create_process_steps(self, process_data: Dict[str, Any]) -> List:
        """Create the detailed process steps section"""
        elements = []
        
        elements.append(Paragraph("Detailed Process Steps", self.styles['SectionHeader']))
        elements.append(Spacer(1, 12))
        
        # Add AI Model Answer section if available - this is the complete response
        if process_data.get('ai_model_answer'):
            elements.append(Paragraph("Complete Process Recommendation:", self.styles['SectionHeader']))
            elements.append(Spacer(1, 8))
            # Split into paragraphs for better formatting
            ai_answer = process_data['ai_model_answer']
            
            # Remove references section - everything after "-----" followed by "### Note" or "Embeddings & Citations"
            # Split by common reference section markers
            reference_markers = [
                '\n### Note\n',
                '\n### Note:',
                '\n**Embeddings & Citations Section**',
                '\nEmbeddings & Citations Section',
                '\nEMBEDDING REFERENCES',
                '\nNOTE: Detailed book references',
                '\n-----'  # If this is followed by Note/References, cut there
            ]
            
            # Find the earliest reference marker
            cut_index = len(ai_answer)
            for marker in reference_markers:
                idx = ai_answer.find(marker)
                if idx != -1 and idx < cut_index:
                    # Check if this marker is followed by reference content
                    after_marker = ai_answer[idx + len(marker):idx + len(marker) + 100].lower()
                    if any(keyword in after_marker for keyword in ['ref ', 'reference', 'citation', 'embedding', 'note']):
                        cut_index = idx
            
            # Also check for pattern: "-----" followed by newline and then "### Note" or reference content
            dash_sep_idx = ai_answer.find('\n-----\n')
            if dash_sep_idx != -1:
                after_dash = ai_answer[dash_sep_idx + 7:dash_sep_idx + 50].lower()
                if any(keyword in after_dash for keyword in ['note', 'ref ', 'reference', 'citation', 'embedding']):
                    if dash_sep_idx < cut_index:
                        cut_index = dash_sep_idx
            
            # Cut the content at the reference section
            if cut_index < len(ai_answer):
                ai_answer = ai_answer[:cut_index].strip()
            
            paragraphs = [p.strip() for p in ai_answer.split('\n\n') if p.strip()]
            for para in paragraphs:
                if para and not para.startswith('Ref ') and not para.startswith('• [Ref'):
                    # Skip lines that are clearly references
                    if not any(marker in para for marker in ['EMBEDDING REFERENCES', 'Detailed book references', 'references.json']):
                        elements.append(Paragraph(para.replace('\n', '<br/>'), self.styles['Justification']))
                        elements.append(Spacer(1, 6))
            elements.append(Spacer(1, 12))
        
        if process_data.get('process_text'):
            # Enhanced process steps parsing
            lines = process_data['process_text'].split('\n')
            current_step = 1
            in_justification = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check for justification section
                if line.startswith('Justification:'):
                    in_justification = True
                    elements.append(Spacer(1, 12))
                    elements.append(Paragraph("Process Justification:", self.styles['SectionHeader']))
                    continue
                
                # Check if it's a numbered step
                if (line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')) or 
                    line.startswith(('1)', '2)', '3)', '4)', '5)', '6)', '7)', '8)', '9)'))):
                    
                    # Clean up the step text
                    step_text = line
                    for prefix in ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', 
                                  '1)', '2)', '3)', '4)', '5)', '6)', '7)', '8)', '9)']:
                        if step_text.startswith(prefix):
                            step_text = step_text[len(prefix):].strip()
                            break
                    
                    elements.append(Paragraph(f"Step {current_step}: {step_text}", self.styles['ProcessStep']))
                    current_step += 1
                elif line and not in_justification:
                    # Additional detail for the current step
                    if line.startswith('-') or line.startswith('•'):
                        # Bullet point
                        clean_line = line[1:].strip()
                        elements.append(Paragraph(f"   • {clean_line}", self.styles['ProcessStep']))
                    else:
                        # Regular detail
                        elements.append(Paragraph(f"   {line}", self.styles['ProcessStep']))
                elif in_justification:
                    # Justification content
                    elements.append(Paragraph(line, self.styles['Justification']))
        
        return elements

    def _create_citations_section(self, process_data: Dict[str, Any]) -> List:
        """Create the citations and references section"""
        elements = []
        
        elements.append(Paragraph("References and Citations", self.styles['SectionHeader']))
        elements.append(Spacer(1, 12))
        
        if process_data.get('citations'):
            citations = process_data['citations']
            
            # Summary with book breakdown
            total_citations = citations.get('total_citations', 0)
            elements.append(Paragraph(f"Total Citations: {total_citations}", self.styles['Normal']))
            elements.append(Spacer(1, 8))
            
            # Book breakdown
            book_counts = {}
            for citation in citations.get('used_references', []):
                book = citation.get('standard', 'Unknown')
                book_counts[book] = book_counts.get(book, 0) + 1
            
            if book_counts:
                elements.append(Paragraph("References by Book:", self.styles['Normal']))
                for book, count in book_counts.items():
                    elements.append(Paragraph(f"• {book}: {count} references", self.styles['Normal']))
                elements.append(Spacer(1, 12))
            
            # Detailed citations with page numbers
            elements.append(Paragraph("Detailed References:", self.styles['Normal']))
            elements.append(Spacer(1, 8))
            
            for i, citation in enumerate(citations.get('used_references', []), 1):
                standard = citation.get('standard', 'Unknown')
                page = citation.get('page', 'N/A')
                text = citation.get('text', '')
                
                elements.append(Paragraph(f"[{i}] {standard} - Page {page}", self.styles['Citation']))
                elements.append(Paragraph(f"    {text[:300]}{'...' if len(text) > 300 else ''}", self.styles['Citation']))
                elements.append(Spacer(1, 6))
            
            # Add justification if available
            if citations.get('justification'):
                elements.append(Spacer(1, 12))
                elements.append(Paragraph("Process Justification:", self.styles['SectionHeader']))
                elements.append(Paragraph(citations['justification'], self.styles['Justification']))
        else:
            # Fallback information
            methodology = process_data.get('methodology_preference', 'N/A')
            elements.append(Paragraph(f"Process based on {methodology} methodology", self.styles['Normal']))
            elements.append(Paragraph("No specific citations available", self.styles['Citation']))
        
        return elements

    def _create_justification_section(self, process_data: Dict[str, Any]) -> List:
        """Create the justification section"""
        elements = []
        
        elements.append(Paragraph("Process Justification", self.styles['SectionHeader']))
        elements.append(Spacer(1, 12))
        
        if process_data.get('citations', {}).get('justification'):
            justification = process_data['citations']['justification']
            elements.append(Paragraph(justification, self.styles['Justification']))
        
        return elements


def generate_process_pdf(process_data: Dict[str, Any], output_path: str = None) -> bytes:
    """
    Convenience function to generate a process PDF document
    
    Args:
        process_data: Dictionary containing process information
        output_path: Optional path to save the PDF file
        
    Returns:
        bytes: PDF document as bytes
    """
    generator = PDFGenerator()
    return generator.generate_process_document(process_data, output_path)
