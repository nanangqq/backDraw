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
                 if type(vent) != ezdxf.entities.insert.Insert and
                 type(vent) != ezdxf.entities.circle.Circle and 
                 type(vent) != ezdxf.entities.arc.Arc and 
                 type(vent) in centerFunctions]
        # if block_name == '통기 PD PS Ø150':
            # print(vents)

        if len(vents):
            if len(vents)>25:
                vents = random.choices(vents, k=24)
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
    'Defpoints'
]

def getFloorName(form_dict, floor_idx):
    return form_dict[floor_idx].get_attrib_text('NAME')

def getFloorOriginPoint(form_dict, floor_idx, axis_X='1', axis_Y='A'):
    form_box = form_dict[floor_idx]
    box_origin = form_box.dxfattribs()['insert']
    dims = getDimsFromBox(form_box)
    return dims.getCoords([axis_X, axis_Y])


blockGoChecked = {}

def checkEntityGo(ent):
    if type(ent)==ezdxf.entities.insert.Insert:
        block = ent.block()
        # print('BLOCK:', block.name)
        if block.name == form_block_name:
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
        
    else:
        if ent.dxfattribs()['layer'] in LAYERS_EXCLUDE:
            return False
        else:
            return True

def genXrefFileName(floor_name):
    floors = ['지하 %s층'%i for i in range(7, 0, -1)] + ['지상 %s층'%i for i in range(1, 19)] + ['옥탑', '지붕']
    floor_idx_map = { floors[i]: i+1 for i in range(len(floors)) }
    floor = [fl for fl in floors if fl in floor_name]
    if len(floor):
        floor_idx = floor_idx_map[floor[0]]
    else:
        floor_idx = 99

    if floor_name in ['옥탑', '지붕']:
        return '%02d_%s'%(floor_idx, floor_name.replace(' ', '') + ' ' + '평면도')
    return '%02d_%s'%(floor_idx, floor_name.replace(' ', '')+'평면도')

def makeFloorBlocks(params):
    data_path = params['filePath']
    raw_file_name = params['fileName']
    doc, msp, ents = read_dxf(data_path)

    forms = filterForms(ents, form_block_name)
    
    form_dict, space_map = getFormDictAndIndex(forms)

    floor_dict = {}
    
    for i in range(len(form_dict)):
        floor_name = getFloorName(form_dict, i)
        floor_origin_point = getFloorOriginPoint(form_dict, i, '1', 'F')
        floor_dict[floor_name] = {
            'origin_point': floor_origin_point
        }
    
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
        floor_block = doc.blocks.new(name=floor_name, base_point=floor_data['origin_point'])
        for ent in floor_data['entities']:
            
            if checkEntityGo(ent):
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

params = json.loads(argv[1])

print(makeFloorBlocks(params))

