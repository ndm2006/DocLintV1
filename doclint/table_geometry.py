"""Shrink explicit inline table geometry to the available section width.

Never change cells, merges, text, order, nested table XML or floating placement.
"""
from lxml import etree as E
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W};Q='{'+W+'}'


def fit_table(table, available):
    if table.find('w:tblPr/w:tblpPr',NS) is not None:
        return None,'Bảng nổi: giữ vị trí và kích thước, chưa kiểm tra bố cục.'
    grid=table.find('w:tblGrid',NS)
    if grid is None:return None,'Bảng thiếu lưới cột: chưa tự thu kích thước.'
    try:widths=[int(n.get(Q+'w','0')) for n in grid]
    except ValueError:return None,'Lưới cột không hợp lệ: giữ nguyên kích thước.'
    if not widths or any(w<=0 for w in widths):return None,'Chưa xác định được chiều rộng cột.'
    props=table.find('w:tblPr',NS)
    width=props.find('w:tblW',NS) if props is not None else None
    indent=props.find('w:tblInd',NS) if props is not None else None
    try:
        explicit=int(width.get(Q+'w','0')) if width is not None and width.get(Q+'type')=='dxa' else sum(widths)
        offset=int(indent.get(Q+'w','0')) if indent is not None else 0
    except ValueError:return None,'Chưa xác định được chiều rộng bảng.'
    if max(sum(widths),explicit)<=available and offset==0:return None,None
    # Skip layouts with omitted leading/trailing grid columns instead of guessing cell positions.
    if table.xpath('./w:tr/w:trPr/w:gridBefore|./w:tr/w:trPr/w:gridAfter',namespaces=NS):
        return None,'Bảng bỏ cột lưới: giữ kích thước và báo chưa kiểm tra bố cục.'
    target=min(available,sum(widths),explicit if explicit>0 else sum(widths))
    scaled=[max(1,round(w*target/sum(widths))) for w in widths]
    scaled[-1]+=target-sum(scaled)
    if scaled[-1]<=0:return None,'Bảng quá nhiều cột để thu an toàn.'
    cells=[]
    for row in table.findall('w:tr',NS):
        column=0
        for cell in row.findall('w:tc',NS):
            span=cell.find('w:tcPr/w:gridSpan',NS)
            try:count=int(span.get(Q+'val','1')) if span is not None else 1
            except ValueError:return None,'Ô gộp không hợp lệ: giữ kích thước.'
            if count<1 or column+count>len(widths):return None,'Ô bảng không khớp lưới: giữ kích thước.'
            cells.append((cell,sum(scaled[column:column+count])));column+=count
        if column!=len(widths):return None,'Hàng bảng không khớp lưới: giữ kích thước.'
    if props is None:props=E.Element(Q+'tblPr');table.insert(0,props)
    def set_width(parent,name,value):
        child=parent.find('w:'+name,NS)
        if child is None:child=E.SubElement(parent,Q+name)
        child.set(Q+'w',str(value));child.set(Q+'type','dxa')
    set_width(props,'tblW',target)
    if indent is not None:set_width(props,'tblInd',0)
    for node,value in zip(grid,scaled):node.set(Q+'w',str(value))
    for cell,value in cells:
        cp=cell.find('w:tcPr',NS)
        if cp is None:cp=E.Element(Q+'tcPr');cell.insert(0,cp)
        set_width(cp,'tcW',value)
        order={'tcW':0,'gridSpan':1,'hMerge':2,'vMerge':3,'tcBorders':4,'shd':5,'noWrap':6,'tcMar':7,'textDirection':8,'tcFitText':9,'vAlign':10}
        cp[:]=sorted(cp,key=lambda n:order.get(E.QName(n).localname,11))
    return {'before_width_twips':max(sum(widths),explicit),'after_width_twips':target,'available_width_twips':available},None


def without_geometry(table):
    """Return a copy with exactly the allowlisted top-level width properties removed."""
    import copy
    table=copy.deepcopy(table)
    for path in ('w:tblPr/w:tblW','w:tblPr/w:tblInd','w:tr/w:tc/w:tcPr/w:tcW'):
        for node in table.findall(path,NS):node.getparent().remove(node)
    for column in table.findall('w:tblGrid/w:gridCol',NS):column.attrib.pop(Q+'w',None)
    # Empty property containers added solely for widths carry no content semantics.
    for path in ('w:tblPr','w:tr/w:tc/w:tcPr'):
        for node in table.findall(path,NS):
            if len(node)==0 and not node.attrib:node.getparent().remove(node)
    return table
