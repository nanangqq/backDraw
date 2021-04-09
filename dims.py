import ezdxf

class Dims:
    def __init__(self, box_origin = ezdxf.math.Vector()):
        self.box_origin = box_origin
        self.verticals = {}
        self.horizons = {}
        self.axisIdxMap = {
            'vertical': 0,
            'horizon': 1
        }
        
        self.registerAxis('1', 3000, isVertical = True)
        self.registerAxis('A', 3000, isVertical = False)
        
    def registerAxis(self, axisNo, distFromBoxOrigin, isVertical = True):
        dists = [0, 0, 0]

        if isVertical:
            direction = 'vertical'
            dists[self.axisIdxMap[direction]] = distFromBoxOrigin
            distVector = ezdxf.math.Vector(dists)
            self.verticals[axisNo] = distVector
        else:
            direction = 'horizon'
            dists[self.axisIdxMap[direction]] = distFromBoxOrigin
            distVector = ezdxf.math.Vector(dists)
            self.horizons[axisNo] = distVector


    def getNewCoords(self, isAbsolute = True):
        if isAbsolute:
            return ezdxf.math.Vector([coord for coord in self.box_origin])
        else:
            return ezdxf.math.Vector()
            
    def getCoords(self, axisNos, isAbsolute = True):
        if len(axisNos) != 2:
            return None
        else:
            verticalNo = [axisNo for axisNo in axisNos if axisNo in self.verticals]
            horizonNo = [axisNo for axisNo in axisNos if axisNo in self.horizons]
            if len(verticalNo) != 1 and len(horizonNo) !=1:
                return None
            else:
                coords = self.getNewCoords(isAbsolute)
                coords += self.verticals[verticalNo[0]]
                coords += self.horizons[horizonNo[0]]
                return coords