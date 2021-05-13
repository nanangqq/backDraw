import ezdxf
from rtree import index
import math
import numpy as np
import random
from sys import argv
import os
import json

from dims import Dims 

# sys.setrecursionlimit(3000)

def getDimsFromBox(box):
    axisInserts = [vent for vent in box.virtual_entities() 
                   if type(vent)==ezdxf.entities.insert.Insert]
    # print(axisInserts)
    box_origin = box.dxfattribs()['insert']
    # print(box_origin)
    dims = Dims(box_origin)
    for axisInsert in axisInserts:
        # print(axisInsert.block().name)
        axisNo = axisInsert.get_attrib_text('NO')
        # print(axisNo)
        if axisNo == '-':
            continue
        else:
            attrs = axisInsert.dxfattribs()
            if 'rotation' in attrs and attrs['rotation']==90:
                isVertical = False
                distFromBoxOrigin = (attrs['insert'] - box_origin)[dims.axisIdxMap['horizon']]
            else:
                isVertical = True
                distFromBoxOrigin = (attrs['insert'] - box_origin)[dims.axisIdxMap['vertical']]
            
            # print(axisNo, distFromBoxOrigin)
            dims.registerAxis(axisNo, distFromBoxOrigin, isVertical)
    
    return dims

def isVertical(axis_NO):
    major_NO = axis_NO.split('.')[0]
    try:
        return type(int(major_NO))==int
    except:
        return False

def getDimsFromAxisBlocks(axis_blocks):
    # print(axis_blocks)
    dims = Dims()

    for axis_block in axis_blocks.values():
        # print(axis_block.dxfattribs()['insert'])
        axis_block_origin = axis_block.dxfattribs()['insert']

        # try:
        for vent in [vent for vent in axis_block.virtual_entities() if type(vent)==ezdxf.entities.insert.Insert]:
            axis_NO = vent.get_attrib_text('NO')
            
            axis_is_vertical = isVertical(axis_NO)
            if axis_is_vertical:
                direction = 'vertical'
            else:
                direction = 'horizon'

            vector_from_box_origin = vent.dxfattribs()['insert'] - axis_block_origin
            dist_from_box_origin = vector_from_box_origin[dims.axisIdxMap[direction]]

            dims.registerAxis(axis_NO, dist_from_box_origin, axis_is_vertical)
        # except:
        #     pass
        # print([[vent.get_attrib_text('NO'), isVertical(vent.get_attrib_text('NO')), vent.dxfattribs()['insert']] for vent in axis_block.virtual_entities() if type(vent)==ezdxf.entities.insert.Insert])
    return dims

def getBlockNameAndInsertPointAndAttrs(insert):
    if type(insert)==ezdxf.entities.insert.Insert:
        attr = insert.dxfattribs()
        return attr['name'], attr['insert'], {k:v for k, v in attr.items() if k not in ['name', 'insert', 'handle', 'owner']}


def read_dxf(path):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    ents = msp.entity_space.entities
    return doc, msp, ents


def getFormBB(formInsert):
    
    vertices = []
    for vent in formInsert.virtual_entities():
        if type(vent)==ezdxf.entities.line.Line:
            attrs = vent.dxf.all_existing_dxf_attribs()
            vertices += [attrs['start'], attrs['end']]
        elif type(vent)==ezdxf.entities.lwpolyline.LWPolyline:
            vertices += [v for v in vent.vertices()]
    
    minX, minY = vertices[0][:2]
    maxX, maxY = vertices[0][:2]
    for v in vertices[1:]:
        if v[0]<minX:
            minX = v[0]
        if v[0]>maxX:
            maxX = v[0]
        if v[1]<minY:
            minY = v[1]
        if v[1]>maxY:
            maxY = v[1]
    
    return minX, minY, maxX, maxY

def getSize(bb):
    return {
        'width': int(bb[2]-bb[0]),
        'height': int(bb[3]-bb[1])
    }

def getFormDictAndIndex(forms):
    form_dict = {}
    space_map = index.Index()
    for i in range(len(forms)):
        formInsert = forms[i]
        form_dict[i] = formInsert
        space_map.insert(i, getFormBB(formInsert))
    return form_dict, space_map


centerFunctions = {}
blockPointFromOrigin = {}

def getHypoCenter(entity):
    if type(entity) in centerFunctions:
        return centerFunctions[type(entity)](entity)
    else:
        #print(entity)
        leftover.append(entity)
    
def getLineCenter(line):
    attrs = line.dxfattribs()
    return (attrs['start']+attrs['end'])/2

centerFunctions[ezdxf.entities.line.Line] = getLineCenter

def getArcPointCoord(center, radius, angle):
    rad = math.radians(angle)
    loc = np.array([math.cos(rad), math.sin(rad)])*radius
    return ezdxf.math.vector.Vector(center) + loc

def getArcCenter(arc):
    attrs = arc.dxfattribs()
    center = attrs['center']
    radius = attrs['radius']
    start = attrs['start_angle']
    end = attrs['end_angle']
    start_point = getArcPointCoord(center, radius, start)
    end_point = getArcPointCoord(center, radius, end)
    return (start_point+end_point)/2

centerFunctions[ezdxf.entities.arc.Arc] = getArcCenter

def getTextPoint(text):
    return text.get_pos()[1]

centerFunctions[ezdxf.entities.text.Text] = getTextPoint

def getPolylinePoint(pl):
    if 'const_width' in pl.dxfattribs():
        pl.set_dxf_attrib('const_width', 0)
        
    vents = [vent for vent in pl.virtual_entities() if type(vent) in centerFunctions and type(vent) != ezdxf.entities.arc.Arc]
    if len(vents)>25:
        vents = random.choices(vents, k=24)
    elif len(vents)==0:
        # print(pl.dxfattribs())
        verts = [ezdxf.math.Vector(v) for v in pl.vertices()]
            # print(v)
            # print(type(v))
            # print(ezdxf.math.Vector(v))
        return sum(verts)/len(verts)
    return sum([getHypoCenter(vent) for vent in vents])/len(vents)

centerFunctions[ezdxf.entities.lwpolyline.LWPolyline] = getPolylinePoint

def getLineEdgeCenter(edge):
    start = ezdxf.math.vector.Vector(edge.start)
    end = ezdxf.math.vector.Vector(edge.end)
    return ezdxf.math.vector.Vector((start+end)/2)

centerFunctions[ezdxf.entities.hatch.LineEdge] = getLineEdgeCenter

def getArcEdgeCenter(edge):
    start_point = getArcPointCoord(edge.center, edge.radius, edge.start_angle)
    end_point = getArcPointCoord(edge.center, edge.radius, edge.end_angle)
    return (start_point+end_point)/2

centerFunctions[ezdxf.entities.hatch.ArcEdge] = getArcEdgeCenter

def getPolylinePathCenter(plpath):
    verts = plpath.vertices
    return sum([ezdxf.math.vector.Vector(v) for v in verts])/len(verts)

centerFunctions[ezdxf.entities.hatch.PolylinePath] = getPolylinePathCenter

def getPathCenter(path):
    edges = path.edges
    if len(edges)>25:
        edges = random.choices(edges, k=24)
    return sum([getHypoCenter(edge) for edge in edges])/len(edges)

centerFunctions[ezdxf.entities.hatch.EdgePath] = getPathCenter

def getHatchPoint(hatch):
    paths = hatch.paths.paths
    if len(paths)>25:
        paths = random.choices(paths, k=24)
    leftpaths.append(paths)
    return sum([getHypoCenter(path) for path in paths])/len(paths)

centerFunctions[ezdxf.entities.hatch.Hatch] = getHatchPoint

def getBlockNameAndInsertPoint(insert):
    if type(insert)==ezdxf.entities.insert.Insert:
        attr = insert.dxfattribs()
        return attr['name'], attr['insert']

def applyMirror(vector, mir):
    return ezdxf.math.Vector(vector[0]*mir, vector[1], vector[2])
    
def getInsertCenter(insert):
    block_name, insert_point, attrs = getBlockNameAndInsertPointAndAttrs(insert)
    
    if block_name in blockPointFromOrigin:
        point_from_block_origin = blockPointFromOrigin[block_name]
        point = insert_point + point_from_block_origin
        
    else:
        block = insert.block()
        # if block_name == '통기 PD PS Ø150':
            # print([vent for vent in insert.virtual_entities()])
        vents = [vent for vent in insert.virtual_entities() 
                 if type(vent) != ezdxf.entities.circle.Circle and 
                 type(vent) != ezdxf.entities.arc.Arc and 
                 type(vent) in centerFunctions] # type(vent) != ezdxf.entities.insert.Insert and
                 # 블록이 해당 도곽 안에 있는지 없는지 체크하는 과정에서, 블록 내부에 있는 요소들의 중심점들을 모아서 평균을 낸
                 # 점으로 그 블록이 도곽 영역 안에 있는지 판단함.
                 # 근데, 블록의 삽입 기준점이 멀리 있는 블록이거나, 미러된 블록의 경우, 내부 요소들의 좌표계산이 약간 이상하게 되는 경우가 있음
                 # 그래서 처음에는 블록이나 호, 원 등을 제외한 요소들만 추려서 점을 계산하고 (호, 원도 블록 안에 들어가 있을 경우 위치 계산할때 뭔가 문제가 있음,,)
                 # 만약 블록, 호, 원 등을 제외한 요소들의 개수가 너무 적으면 안에 있는 블록을 깨버리는 방식으로 점을 찾아갔었는데
                 # 블록을 깰 때, 그 블록 안에 (미러된 블록 혹은 사용자정의속성이 있는 블록)이 들어있으면 깼을 때 안에 있던 블록의 회전이나 미러값이 제대로 반영되지 않는 것 같음.
                 # 일단 지금은 기준점 이상한 블록이(주로 외주업체에서 사용하던 블록,, 배관, 기계 이런 것들) 없다고 가정하고
                 # 처음 블록의 요소들을 추리는 과정에서 블록도 포함시켜서 진행.. 210513
        # if block_name == '통기 PD PS Ø150':
            # print(vents)

        if len(vents):
            if len(vents)>1: # 25개에서 2개 이상으로 바꿈,,,
                vents = random.choices(vents, k=1)
            point = sum([getHypoCenter(vent) for vent in vents])/len(vents)
        else:
            insertsInBlock = [ent for ent in block.entity_space.entities if type(ent) == ezdxf.entities.insert.Insert]
            # if block_name == '통기 PD PS Ø150':
                # print(insertsInBlock)
            for ins in insertsInBlock:
                ins.explode()
            point = getInsertCenter(insert)
            
        point_from_block_origin = point - insert_point
        blockPointFromOrigin[block_name] = point_from_block_origin

    #     block.add_point(point_from_block_origin)
    #     block.add_text(block_name, {'insert':point_from_block_origin, 'height': 200})

    # block_points.append({
    #     'block_name': block_name,
    #     'point': point
    # })


    return point

centerFunctions[ezdxf.entities.insert.Insert] = getInsertCenter

def getDimPoint(dim):
    return dim.dxfattribs()['defpoint']

centerFunctions[ezdxf.entities.dimension.Dimension] = getDimPoint

def getCircleCenter(circle):
    return circle.dxfattribs()['center']

centerFunctions[ezdxf.entities.circle.Circle] = getCircleCenter



def filterForms(ents, block_name):
    return [ent for ent in ents if 'block' in dir(ent) and ent.block().name==block_name]

def getIntersectingForms(ent, space_map):
    loc = getHypoCenter(ent)
    if loc:
        return [bb_id for bb_id in space_map.intersection((loc[0], loc[1], loc[0], loc[1]))]
    else:
        return []

LAYERS_EXCLUDE=[
    'A-ANNOT',
    'A-WALL-INSUL',
    'A-WALL-PATT',
    'Defpoints',
    '00_REV',
    '00_CHECK_SIZE',
    'A-FORM',
    'A-SYMB-RN'
]

def getFloorName(form_dict, floor_idx):
    return form_dict[floor_idx].get_attrib_text('도면명1')

# def getFloorOriginPoint(form_dict, floor_idx, axis_X='1', axis_Y='A'):
#     form_box = form_dict[floor_idx]
#     # box_origin = form_box.dxfattribs()['insert']
#     dims = getDimsFromBox(form_box)
#     return dims.getCoords([axis_X, axis_Y])


blockGoChecked = {}

def checkEntityGo(ent):
    if type(ent)==ezdxf.entities.insert.Insert:
        block = ent.block()
        # print('BLOCK:', block.name)
        if block.name == form_block_name:
            return False
        elif block.name in dict(axis_block_names, **{'KM':1,'기준점_대지':1}):
            return False
        elif ent.dxfattribs()['layer'] in LAYERS_EXCLUDE:
            return False
        elif block.name in blockGoChecked:
            return True
        else:
            othersInBlock = [b_ent for b_ent in block.entity_space.entities if type(b_ent)!=ezdxf.entities.insert.Insert]
            for b_ent in othersInBlock:
                # print(b_ent, b_ent.dxfattribs()['layer'])
                if not checkEntityGo(b_ent):
                    # print('removed', b_ent)
                    block.unlink_entity(b_ent)

            insertsInBlock = [b_ent for b_ent in block.entity_space.entities if type(b_ent)==ezdxf.entities.insert.Insert]
            for b_ins in insertsInBlock:
                if not checkEntityGo(b_ins):
                    block.unlink_entity(b_ins)

            blockGoChecked[block.name] = True
            return True

    elif type(ent) in {ezdxf.entities.mtext.MText: 1, ezdxf.entities.text.Text:1}:
        return False

    else:
        if ent.dxfattribs()['layer'] in LAYERS_EXCLUDE:
            return False
        else:
            return True

def genXrefFileName(floor_name):
    floors = ['지하%s층'%i for i in range(7, 0, -1)] + ['지상%s층'%i for i in range(1, 19)] + ['옥탑', '옥탑지붕']
    floor_idx_map = { floors[i]: i+1 for i in range(len(floors)) }
    floor = [fl for fl in floors if fl in floor_name]
    if len(floor):
        floor_idx = floor_idx_map[max(floor)]
    else:
        floor_idx = 99

    # if floor_name in ['옥탑', '지붕']:
    if floor_idx > 25:
        return '%02d_%s'%(floor_idx, floor_name)
    return '%02d_%s'%(floor_idx, floor_name.replace(' ', ''))

def getFloorBlockOriginPoint(form_dict, floor_idx, dims, axis_X='1', axis_Y='A'):
    form_box = form_dict[floor_idx]
    box_origin = form_box.dxfattribs()['insert']
    dims.box_origin = box_origin
    return dims.getCoords([axis_X, axis_Y])

def makeFloorBlocks(params):
    data_path = params['filePath']
    raw_file_name = params['fileName']
    doc, msp, ents = read_dxf(data_path)

    forms = filterForms(ents, form_block_name)
    
    form_dict, space_map = getFormDictAndIndex(forms)


    axis_blocks = { ent.block().name: ent for ent in ents if 
        type(ent)==ezdxf.entities.insert.Insert 
        and ent.block().name in axis_block_names }

    dims = getDimsFromAxisBlocks(axis_blocks)
    # print(dims.verticals)
    # print(dims.horizons)

    # 폼별로 블록 기준점 가져오기    
    floor_dict = {}
    for i in range(len(form_dict)):
        floor_name = getFloorName(form_dict, i)
        
        # floor_origin_point = getFloorOriginPoint(form_dict, i, '1', 'F')
        floor_origin_point = getFloorBlockOriginPoint(form_dict, i, dims, '1', 'F')
        
        floor_dict[floor_name] = {
            'origin_point': floor_origin_point
        }

    # return floor_dict
    
    for ent in ents:
        form_idxes = getIntersectingForms(ent, space_map)
        if len(form_idxes)==1:
            intersecting_floor_name = getFloorName(form_dict, form_idxes[0])
            
            if 'entities' in floor_dict[intersecting_floor_name]:
                floor_dict[intersecting_floor_name]['entities'].append(ent)
            else:
                floor_dict[intersecting_floor_name]['entities'] = [ent]


    wb_script = []

    for floor_name, floor_data in floor_dict.items():
        if floor_name =='(SGL-00,000)':
            continue

        # floor_block = doc.blocks.new(name=floor_name, base_point=floor_data['origin_point'])
        floor_block = doc.blocks.new(name=floor_name) # 블록 만들때 기준점 원점으로 변경,, 대신 블록에 넣을 엔터티들을 원점 근처 좌표로 이동시킴
        for ent in floor_data['entities']:
            
            if checkEntityGo(ent):
                # 블록 잡기 전에 기준점이 원점이 되도록 위치 이동_0428 -> 새로 만든 xref에서 xclip 할 때 좌표 변화 안생기도록,,
                dx, dy, dz = floor_data['origin_point']
                ent.translate(-dx, -dy, -dz)

                msp.unlink_entity(ent)
                floor_block.add_entity(ent)
            else:
                msp.unlink_entity(ent)
                
        msp.add_blockref(floor_name, floor_data['origin_point'])
        wb_script += [
            'wblock',
            '"C:\\Users\\Public\\%s.dwg"'%genXrefFileName(floor_name),
            '"%s"'%floor_name
        ]
    
    output_file_name = '_fl_blocks.'.join(raw_file_name.split('.'))
    static_dir = 'static'
    output_file_path = os.path.join(static_dir, output_file_name)
    doc.saveas(output_file_path)

    output_script_name = raw_file_name.split('.')[0] + '_wb.scr'
    output_script_path = os.path.join(static_dir, output_script_name)
    with open(output_script_path, 'w', encoding='ms949') as f:
        f.write('\n'.join(wb_script)+'\n')

    return '|'.join([
        output_file_path.replace('static', 'files'), 
        output_script_path.replace('static', 'files')
        ])

leftover = []
leftpaths = []
block_points = []
form_block_name = 'NEED_FORM_VER3'
axis_block_names = {axis_block_name:1 for axis_block_name in ['Axis_1', 'Axis_2', 'Axis_3', 'Axis_4', 'Axis_Corner']}

params = json.loads(argv[1])

print(makeFloorBlocks(params))

