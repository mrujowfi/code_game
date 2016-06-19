#coding=utf-8
import sys
import copy
import timing
import time
from selenium import webdriver
import traceback
import datetime

g_version = 'v2.2'
'''
气眼检测 v1.0
波纹探测墙 v1.1
波纹探测岛 v2.0
探索顺序3,2,4,1 v2.1
初级残影检测 v2.2
'''
global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow, sum_walk, sum_second


def init(question):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow, sum_walk, sum_second
    arg = question.replace('\n', '')
    line = int(arg.split('&')[1].split('=')[1])
    row = int(arg.split('&')[2].split('=')[1])
    pos = arg.split('&')[3].split('=')[1]
    house = [[0 for i in range(row)] for j in range(line)]
    house_list = []
    history = ''
    failed_set = set()
    sys.setrecursionlimit(1000*line*row)
    num_map = {'num_-1': 0, 'num_0': 0, 'num_1': 0, 'num_2': 0, 'num_3': 0, 'num_4': 0}
    shadow = [[[1 for k in range(4)] for i in range(row)] for j in range(line)]#(up, down, left, right)
    sum_second = 0
    sum_walk = 0

    #init each position
    for each in range(len(pos)):
        j = each%row
        i = (each-j)/row
        if pos[each] == '1':
            house[i][j] = -1
            num_map['num_-1'] += 1
        else:
            house[i][j] = 0

    #count position value
    for i in range(line):
        for j in range(row):
            if house[i][j] >= 0:
                posCount(house, i, j, num_map, True)


    print datetime.datetime.now().strftime("%Y%m%d-%H%M%S.%f")
    print arg
    print line, row
    print_house(house)


def print_house(temp_house):
    print '   ',
    for j in range(len(temp_house[0])):
        print '%3d ' % j,
    print ' '
    for i in range(len(temp_house)):
        each = temp_house[i]
        print '%3d' % i,
        for each2 in each:
            print '%3d ' % each2,
        print ' '


#count one position value
def posCount(temp_house, i, j, temp_num_map, firstInit=False):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow

    n = 0
    if i-1 >= 0 and temp_house[i-1][j] >= 0:
        n += 1
    if i+1 < line and temp_house[i+1][j] >= 0:
        n += 1
    if j-1 >= 0 and temp_house[i][j-1] >= 0:
        n += 1
    if j+1 < row and temp_house[i][j+1] >= 0:
        n += 1
    if not firstInit:
        temp_num_map['num_'+str(temp_house[i][j])] -= 1
    temp_num_map['num_'+str(n)] += 1
    temp_house[i][j] = n


def multiArea(temp_house, block_line, block_row):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow

    #wave all blocks, and check if A-B==0 or A-B==2
    #wide is highest when travelling
    block_now = copy.deepcopy(temp_house)
    selected_list = []
    selected_list.append((block_line, block_row, 1))#(line, row, depth)
    search_wall = {'state': 0, 'cross': 0}

    #select all linked blocks
    #print 'block', block_line, block_row
    #print_house(block_now)
    try:
        block_now[block_line][block_row] = -2
        if block_line == 0 or block_line == line-1 or block_row == 0 or block_row == row-1:
            search_wall['wall-2'] = 1
        result = travelBlock(block_now, selected_list, search_wall)
    except RuntimeError, e:
        print 'error', e
        result = False

    #analyse wall to wall
    if not result:
        result = analyzeMulti(block_now)
        if result:
            #print 'analyse block true'
            #print_house(block_now)
            pass
    else:
        #print 'travel block true'
        #print_house(block_now)
        pass


    #print result
    #print_house(block_now)

    return result


def travelBlock(block_now, selected_list, search_wall):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow

    if len(selected_list) == 0:
        return False
    i, j, depth = selected_list.pop(0)

    #print_house(block_now)

    #select all blocks nearby
    peer_block = 0
    if i > 0:
        if block_now[i-1][j] == -1:
            #up
            block_now[i-1][j] = -1 - (depth+1)
            selected_list.append((i-1, j, depth+1))
        #elif block_now[i-1][j] == block_now[i][j]:
        #    peer_block += 1
    if i+1 < line:
        if block_now[i+1][j] == -1:
            #down
            block_now[i+1][j] = -1 - (depth+1)
            selected_list.append((i+1, j, depth+1))
        #elif block_now[i+1][j] == block_now[i][j]:
        #    peer_block += 1
    if j > 0:
        if block_now[i][j-1] == -1:
            #left
            block_now[i][j-1] = -1 - (depth+1)
            selected_list.append((i, j-1, depth+1))
        #elif block_now[i][j-1] == block_now[i][j]:
        #    peer_block += 1
    if j+1 < row:
        if block_now[i][j+1] == -1:
            #right
            block_now[i][j+1] = -1 - (depth+1)
            selected_list.append((i, j+1, depth+1))
        #elif block_now[i][j+1] == block_now[i][j]:
        #    peer_block += 1

    if peer_block > 2:
        search_wall['cross'+str(-1 - (depth))] = 1
    if search_wall.__contains__('cross'+str(-1 - (depth-1))):
        search_wall['cross'] += 1
        if search_wall['cross'] > 1:
            return True
        elif search_wall['cross'] == 1 and search_wall['state'] > 0:
            return True

    if i > 0 and j > 0 and block_now[i-1][j-1] == -1:
        #up,left
        block_now[i-1][j-1] = -1 - (depth+1)
        selected_list.append((i-1, j-1, depth+1))
    if i+1 < line and j > 0 and block_now[i+1][j-1] == -1:
        #down,left
        block_now[i+1][j-1] = -1 - (depth+1)
        selected_list.append((i+1, j-1, depth+1))
    if i > 0 and j+1 < row and block_now[i-1][j+1] == -1:
        #up,right
        block_now[i-1][j+1] = -1 - (depth+1)
        selected_list.append((i-1, j+1, depth+1))
    if i+1 < line and j+1 < row and block_now[i+1][j+1] == -1:
        #down,right
        block_now[i+1][j+1] = -1 - (depth+1)
        selected_list.append((i+1, j+1, depth+1))

    #mark this wave if wall
    if i == 0 or i == line-1 or j == 0 or j == row-1:
        search_wall['wall'+str(-1 - (depth))] = 1
        #print 'walled', (-1 - (depth))

    if search_wall['state'] == 0:
        #searching wall1
        if search_wall.__contains__('wall'+str(-1 - (depth-1))):
            if search_wall['cross'] > 1:
                return True
            #print (-1 - (depth)), '0->1'
            search_wall['state'] = 1
    elif search_wall['state'] == 1:
        #in wall1
        if search_wall['cross'] > 1:
            return True
        if search_wall.__contains__('wall'+str(-1 - (depth-1))):
            pass
        else:
            #print (-1 - (depth)), '1->2'
            search_wall['state'] = 2
    elif search_wall['state'] == 2:
        #searching wall2
        if search_wall['cross'] > 1:
            return True
        if search_wall.__contains__('wall'+str(-1 - (depth-1))):
            #print (-1 - (depth)), '2->Ture'
            return True

    if len(selected_list) == 0:
        if search_wall['state'] == 2:
            #searching wall2
            if search_wall.__contains__('wall'+str(-1 - (depth))):
                #print (-1 - depth), '2->Ture'
                return True

    return travelBlock(block_now, selected_list, search_wall)


def analyzeMulti(block_now):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow

    target = 0
    searching = True
    if block_now[0][0] < -1:
        #selected
        for j in range(row):
            if searching:
                if block_now[0][j] >= -1:
                    target += 1
                    if target == 2:
                        return True
                    searching = False
            else:
                if block_now[0][j] < -1:
                    searching = True
        for i in range(line):
            if searching:
                if block_now[i][row-1] >= -1:
                    target += 1
                    if target == 2:
                        return True
                    searching = False
            else:
                if block_now[i][row-1] < -1:
                    searching = True
        for j in range(row-1, -1, -1):
            if searching:
                if block_now[line-1][j] >= -1:
                    target += 1
                    if target == 2:
                        return True
                    searching = False
            else:
                if block_now[line-1][j] < -1:
                    searching = True
        for i in range(line-1, -1, -1):
            if searching:
                if block_now[i][0] >= -1:
                    target += 1
                    if target == 2:
                        return True
                    searching = False
            else:
                if block_now[i][0] < -1:
                    searching = True
    else:
        #not selected
        for j in range(row):
            if searching:
                if block_now[0][j] < -1:
                    target += 1
                    if target == 2:
                        return True
                    searching = False
            else:
                if block_now[0][j] >= -1:
                    searching = True
        for i in range(line):
            if searching:
                if block_now[i][row-1] < -1:
                    target += 1
                    if target == 2:
                        return True
                    searching = False
            else:
                if block_now[i][row-1] >= -1:
                    searching = True
        for j in range(row-1, -1, -1):
            if searching:
                if block_now[line-1][j] < -1:
                    target += 1
                    if target == 2:
                        return True
                    searching = False
            else:
                if block_now[line-1][j] >= -1:
                    searching = True
        for i in range(line-1, -1, -1):
            if searching:
                if block_now[i][0] < -1:
                    target += 1
                    if target == 2:
                        return True
                    searching = False
            else:
                if block_now[i][0] >= -1:
                    searching = True

    return False


def areYouOK(temp_house, block_line, block_row, temp_num_map, depth):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow

    num_1, num0, num1, num2, num3, num4 = (temp_num_map['num_-1'], temp_num_map['num_0'], temp_num_map['num_1'], temp_num_map['num_2'], temp_num_map['num_3'], temp_num_map['num_4'])
    #print num_1, num0, num1, num2, num3, num4

    #sure
    if num0 == 1 and num1 == 0 and num2 == 0 and num3 == 0 and num4 == 0:
        return True
    if num0 > 0:
        return False
    if num1 > 2:
        return False
    if num0 == 0 and num3 == 0 and num4 == 0:
        return None
    #if num_1*4>line*row and num_1*2<line*row and block_line!=None and block_row!=None and multiArea(temp_house, block_line, block_row):
    #    return False
    if depth % 3 == 0 and multiArea(temp_house, block_line, block_row):
        return False

    #possibly
    return None


def start():
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow, sum_walk, sum_second

    #origin_house at house_list[0]

    #print travel(2, 2, 1)
    '''
    house_list.append((copy.deepcopy(house), copy.deepcopy(num_map)))
    history = ''
    i = 30
    j = 6
    result = travel_first(i, j, 1)
    if result[0]:
        url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+history
        print url
    '''
    print 'search 3'
    house_list.append((copy.deepcopy(house), copy.deepcopy(num_map)))
    for i in range(line):
        for j in range(row):
            if house[i][j] == 3:
                sum_walk += 1
                #print '%d,%d\r' % (i, j),
                print 'walk', i, j
                history = ''
                result = travel_first(i, j, 1)
                if result[0]:
                    url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+history
                    print url
                    return url
    sum_second += timing.stop()
    timing.start()


    print 'search 2'
    del house_list[:]
    house_list = []
    house_list.append((copy.deepcopy(house), copy.deepcopy(num_map)))
    for i in range(line):
        for j in range(row):
            if house[i][j] == 2:
                sum_walk += 1
                #print '%d,%d\r' % (i, j),
                print 'walk', i, j
                history = ''
                result = travel_first(i, j, 1)
                if result[0]:
                    url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+history
                    print url
                    return url
    sum_second += timing.stop()
    timing.start()


    print 'search 1,4'
    del house_list[:]
    house_list = []
    house_list.append((copy.deepcopy(house), copy.deepcopy(num_map)))
    for i in range(line):
        for j in range(row):
            if house[i][j] == 4 or house[i][j] == 1:
                sum_walk += 1
                #print '%d,%d\r' % (i, j),
                print 'walk', i, j
                history = ''
                result = travel_first(i, j, 1)
                if result[0]:
                    url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+history
                    print url
                    return url

    return None


#move from (pos_line, pos_row)
#return (result, (ul, ur, dl, dr))
def travel_first(pos_line, pos_row, depth):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow

    result = (False, ((0, 0), (0, 0)))
    a_house, a_num_map = house_list[depth-1]
    house_now = copy.deepcopy(a_house)
    num_map_now = copy.deepcopy(a_num_map)
    this_shadow_line = [0, 0, 0, 0]#for up, down, left, right count


    #print pos_line, pos_row
    #print_house(house_now)
    #move up
    #if shadow[pos_line][pos_row][0] == 0:
    #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 0)
    if shadow[pos_line][pos_row][0] == 1 and pos_line-1 >= 0 and house_now[pos_line-1][pos_row] >= 0:
        no_shadow = False#flag for not use shadow because eye analyse
        house_up = copy.deepcopy(house_now)
        num_map_up = copy.deepcopy(num_map_now)
        inc = 1
        while pos_line-inc >= 0 and house_up[pos_line-inc][pos_row] >= 0:
            num_map_up['num_'+str(house_up[pos_line-(inc-1)][pos_row])] -= 1
            num_map_up['num_'+str(-1)] += 1
            house_up[pos_line-(inc-1)][pos_row] = -1
            this_shadow_line[0] += 1
            inc+=1
        #recount value
        for i in range(pos_line-inc if pos_line-inc>=0 else 0, (pos_line+2) if pos_line+1<line else line):
            for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<row else [pos_row,]:
                if house_up[i][j] >= 0:
                    posCount(house_up, i, j, num_map_up)
                    if house_up[i][j] == 0 or house_up[i][j] == 1:
                        no_shadow = True
        history = history[:depth-1]+'u'
        if depth % 100 == 0:
            #print history
            pass
        #print_house(house_up)
        house_list = house_list[:depth]+[(house_up,num_map_up),]
        result = travel(pos_line-(inc-1), pos_row, depth+1)
        shadow_line_excluded = excludeShadowUp(((pos_line-this_shadow_line[0], pos_row), (pos_line, pos_row)), result[1])
        #print result[1], shadow_line_excluded
        if no_shadow is False and shadow_line_excluded is not None:
            for step in range(shadow_line_excluded[0][0], shadow_line_excluded[1][0]+1):
                shadow[step][pos_row][0] = 0
        if result[0]:
            return result

    #move down
    #if shadow[pos_line][pos_row][1] == 0:
    #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 1)
    if shadow[pos_line][pos_row][1] == 1 and pos_line+1 < line and house_now[pos_line+1][pos_row] >= 0:
        no_shadow = False#flag for not use shadow because eye analyse
        house_down = copy.deepcopy(house_now)
        num_map_down = copy.deepcopy(num_map_now)
        inc = 1
        while pos_line+inc < line and house_down[pos_line+inc][pos_row] >= 0:
            num_map_down['num_'+str(house_down[pos_line+(inc-1)][pos_row])] -= 1
            num_map_down['num_'+str(-1)] += 1
            house_down[pos_line+(inc-1)][pos_row] = -1
            this_shadow_line[1] += 1
            inc+=1
        #recount value
        for i in range(pos_line-1 if pos_line-1>=0 else 0, (pos_line+inc) if pos_line+inc<line else line):
            for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<row else [pos_row,]:
                if house_down[i][j] >= 0:
                    posCount(house_down, i, j, num_map_down)
                    if house_down[i][j] == 0 or house_down[i][j] == 1:
                        no_shadow = True
        history = history[:depth-1]+'d'
        if depth % 100 == 0:
            #print history
            pass
        #print_house(house_down)
        house_list = house_list[:depth]+[(house_down,num_map_down),]
        result = travel(pos_line+(inc-1), pos_row, depth+1)
        shadow_line_excluded = excludeShadowDown(((pos_line, pos_row), (pos_line+this_shadow_line[1], pos_row)), result[1])
        #print result[1], shadow_line_excluded
        if no_shadow is False and shadow_line_excluded is not None:
            for step in range(shadow_line_excluded[0][0], shadow_line_excluded[1][0]+1):
                #if step == '31' and pos_row == 6:
                #print 'close', pos_line, pos_row, step, pos_row, this_shadow_line, shadow_line_excluded
                shadow[step][pos_row][1] = 0
        if result[0]:
            return result

    #move left
    #if shadow[pos_line][pos_row][2] == 0:
    #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 2)
    if shadow[pos_line][pos_row][2] == 1 and pos_row-1 >= 0 and house_now[pos_line][pos_row-1] >= 0:
        no_shadow = False#flag for not use shadow because eye analyse
        house_left = copy.deepcopy(house_now)
        num_map_left = copy.deepcopy(num_map_now)
        inc = 1
        while pos_row-inc >= 0 and house_left[pos_line][pos_row-inc] >= 0:
            num_map_left['num_'+str(house_left[pos_line][pos_row-(inc-1)])] -= 1
            num_map_left['num_'+str(-1)] += 1
            house_left[pos_line][pos_row-(inc-1)] = -1
            this_shadow_line[2] += 1
            inc+=1
        #recount value
        for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<line else [pos_line,]:
            for j in range(pos_row-inc if pos_row-inc>=0 else 0, (pos_row+2) if pos_row+1<row else row):
                if house_left[i][j] >= 0:
                    posCount(house_left, i, j, num_map_left)
                    if house_left[i][j] == 0 or house_left[i][j] == 1:
                        no_shadow = True
        history = history[:depth-1]+'l'
        if depth % 100 == 0:
            #print history
            pass
        #print_house(house_left)
        house_list = house_list[:depth]+[(house_left,num_map_left),]
        result = travel(pos_line, pos_row-(inc-1), depth+1)
        shadow_line_excluded = excludeShadowLeft(((pos_line, pos_row-this_shadow_line[2]), (pos_line, pos_row)), result[1])
        #print result[1], shadow_line_excluded
        if no_shadow is False and shadow_line_excluded is not None:
            for step in range(shadow_line_excluded[0][1], shadow_line_excluded[1][1]+1):
                shadow[pos_line][step][2] = 0
        if result[0]:
            return result

    #move right
    #if shadow[pos_line][pos_row][3] == 0:
    #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 3)
    if shadow[pos_line][pos_row][3] == 1 and pos_row+1 < row and house_now[pos_line][pos_row+1] >= 0:
        no_shadow = False#flag for not use shadow because eye analyse
        house_right = copy.deepcopy(house_now)
        num_map_right = copy.deepcopy(num_map_now)
        inc = 1
        while pos_row+inc < row and house_right[pos_line][pos_row+inc] >= 0:
            num_map_right['num_'+str(house_right[pos_line][pos_row+(inc-1)])] -= 1
            num_map_right['num_'+str(-1)] += 1
            house_right[pos_line][pos_row+(inc-1)] = -1
            this_shadow_line[3] += 1
            inc+=1
        #recount value
        for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<line else [pos_line,]:
            for j in range(pos_row-1 if pos_row-1>0 else 0, (pos_row+inc) if pos_row+inc<row else row):
                if house_right[i][j] >= 0:
                    posCount(house_right, i, j, num_map_right)
                    if house_right[i][j] == 0 or house_right[i][j] == 1:
                        no_shadow = True
        history = history[:depth-1]+'r'
        if depth % 100 == 0:
            #print history
            pass
        #print_house(house_right)
        house_list = house_list[:depth]+[(house_right,num_map_right),]
        result = travel(pos_line, pos_row+(inc-1), depth+1)
        shadow_line_excluded = excludeShadowRight(((pos_line, pos_row), (pos_line, pos_row+this_shadow_line[3])), result[1])
        #print result[1], shadow_line_excluded
        if no_shadow is False and shadow_line_excluded is not None:
            for step in range(shadow_line_excluded[0][1], shadow_line_excluded[1][1]+1):
                shadow[pos_line][step][3] = 0
        if result[0]:
            return result

    return result


#move from (pos_line, pos_row)
#return (result, (ul, dr))
def travel(pos_line, pos_row, depth):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow

    result = (False, ((0, 0), (0, 0)))
    this_shadow = ((pos_line, pos_row), (pos_line, pos_row))#ul, dr
    #this_shadow_line = {'ul': {'line': pos_line, 'row': pos_row}, 'dr': {'line': pos_line, 'row': pos_row}}#ul, dr
    this_shadow_line = [0, 0, 0, 0]#for up, down, left, right count
    a_house, a_num_map = house_list[depth-1]
    house_now = copy.deepcopy(a_house)
    num_map_now = copy.deepcopy(a_num_map)
    ok = areYouOK(house_now, pos_line, pos_row, num_map_now, depth)
    if ok==False:
        result = (False, ((pos_line, pos_row), (pos_line, pos_row)))
        return result
    elif ok==True:
        result = (True, ((pos_line, pos_row), (pos_line, pos_row)))
        return result
    #return None

    #move up
    if pos_line-1 >= 0 and house_now[pos_line-1][pos_row] >= 0:
        house_up = copy.deepcopy(house_now)
        num_map_up = copy.deepcopy(num_map_now)
        inc = 1
        while pos_line-inc >= 0 and house_up[pos_line-inc][pos_row] >= 0:
            num_map_up['num_'+str(house_up[pos_line-(inc-1)][pos_row])] -= 1
            num_map_up['num_'+str(-1)] += 1
            house_up[pos_line-(inc-1)][pos_row] = -1
            this_shadow_line[0] += 1
            inc+=1
        #recount value
        for i in range(pos_line-inc if pos_line-inc>=0 else 0, (pos_line+2) if pos_line+1<line else line):
            for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<row else [pos_row,]:
                if house_up[i][j] >= 0:
                    posCount(house_up, i, j, num_map_up)
        history = history[:depth-1]+'u'
        if depth % 100 == 0:
            #print history
            pass
        #print_house(house_up)
        house_list = house_list[:depth]+[(house_up,num_map_up),]
        result = travel(pos_line-(inc-1), pos_row, depth+1)
        this_shadow = mergeShadow(mergeShadow(((pos_line - this_shadow_line[0], pos_row), (pos_line, pos_row)), result[1]), this_shadow)
        #if depth == 2:
        #    print 'lgbu', pos_line, pos_row, this_shadow
        if result[0]:
            result = (True, this_shadow)
            return result

    #move down
    if pos_line+1 < line and house_now[pos_line+1][pos_row] >= 0:
        house_down = copy.deepcopy(house_now)
        num_map_down = copy.deepcopy(num_map_now)
        inc = 1
        while pos_line+inc < line and house_down[pos_line+inc][pos_row] >= 0:
            num_map_down['num_'+str(house_down[pos_line+(inc-1)][pos_row])] -= 1
            num_map_down['num_'+str(-1)] += 1
            house_down[pos_line+(inc-1)][pos_row] = -1
            this_shadow_line[1] += 1
            inc+=1
        #recount value
        for i in range(pos_line-1 if pos_line-1>=0 else 0, (pos_line+inc) if pos_line+inc<line else line):
            for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<row else [pos_row,]:
                if house_down[i][j] >= 0:
                    posCount(house_down, i, j, num_map_down)
        history = history[:depth-1]+'d'
        if depth % 100 == 0:
            #print history
            pass
        #print_house(house_down)
        house_list = house_list[:depth]+[(house_down,num_map_down),]
        result = travel(pos_line+(inc-1), pos_row, depth+1)
        this_shadow = mergeShadow(mergeShadow(((pos_line, pos_row), (pos_line + this_shadow_line[1], pos_row)), result[1]), this_shadow)
        #if depth == 2:
        #    print 'lgbd', pos_line, pos_row, this_shadow
        if result[0]:
            result = (True, this_shadow)
            return result

    #move left
    if pos_row-1 >= 0 and house_now[pos_line][pos_row-1] >= 0:
        house_left = copy.deepcopy(house_now)
        num_map_left = copy.deepcopy(num_map_now)
        inc = 1
        while pos_row-inc >= 0 and house_left[pos_line][pos_row-inc] >= 0:
            num_map_left['num_'+str(house_left[pos_line][pos_row-(inc-1)])] -= 1
            num_map_left['num_'+str(-1)] += 1
            house_left[pos_line][pos_row-(inc-1)] = -1
            this_shadow_line[2] += 1
            inc+=1
        #recount value
        for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<line else [pos_line,]:
            for j in range(pos_row-inc if pos_row-inc>=0 else 0, (pos_row+2) if pos_row+1<row else row):
                if house_left[i][j] >= 0:
                    posCount(house_left, i, j, num_map_left)
        history = history[:depth-1]+'l'
        if depth % 100 == 0:
            #print history
            pass
        #print_house(house_left)
        house_list = house_list[:depth]+[(house_left,num_map_left),]
        result = travel(pos_line, pos_row-(inc-1), depth+1)
        this_shadow = mergeShadow(mergeShadow(((pos_line, pos_row - this_shadow_line[2]), (pos_line, pos_row)), result[1]), this_shadow)
        #if depth == 2:
        #    print 'lgbl', pos_line, pos_row, depth, this_shadow, result[1]
        if result[0]:
            result = (True, this_shadow)
            return result

    #move right
    if pos_row+1 < row and house_now[pos_line][pos_row+1] >= 0:
        house_right = copy.deepcopy(house_now)
        num_map_right = copy.deepcopy(num_map_now)
        inc = 1
        while pos_row+inc < row and house_right[pos_line][pos_row+inc] >= 0:
            num_map_right['num_'+str(house_right[pos_line][pos_row+(inc-1)])] -= 1
            num_map_right['num_'+str(-1)] += 1
            house_right[pos_line][pos_row+(inc-1)] = -1
            this_shadow_line[3] += 1
            inc+=1
        #recount value
        for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<line else [pos_line,]:
            for j in range(pos_row-1 if pos_row-1>0 else 0, (pos_row+inc) if pos_row+inc<row else row):
                if house_right[i][j] >= 0:
                    posCount(house_right, i, j, num_map_right)
        history = history[:depth-1]+'r'
        if depth % 100 == 0:
            #print history
            pass
        #print_house(house_right)
        house_list = house_list[:depth]+[(house_right,num_map_right),]
        result = travel(pos_line, pos_row+(inc-1), depth+1)
        this_shadow = mergeShadow(mergeShadow(((pos_line, pos_row), (pos_line, pos_row - this_shadow_line[3])), result[1]), this_shadow)
        #if depth == 2:
        #    print 'lgbr', pos_line, pos_row, depth, this_shadow, result[1]
        if result[0]:
            result = (True, this_shadow)
            return result

    result = (False, this_shadow)
    return result

def mergeShadow(sa, sb):
    sr = ((sa[0][0] if sa[0][0]<sb[0][0] else sb[0][0], sa[0][1] if sa[0][1]<sb[0][1] else sb[0][1]), (sa[1][0] if sa[1][0]>sb[1][0] else sb[1][0], sa[1][1] if sa[1][1]>sb[1][1] else sb[1][1]))
    return sr

def excludeShadowUp(l, s):
    if l[1][0] > s[1][0]:
        return ((s[1][0]+1, l[1][1]), (l[1][0], l[1][1]))
    return None

def excludeShadowDown(l, s):
    if l[0][0] < s[0][0]:
        return ((l[0][0], l[0][1]), (s[0][0]-1, l[0][1]))
    return None

def excludeShadowLeft(l, s):
    if l[1][1] > s[1][1]:
        return ((l[1][0], s[1][1]+1), (l[1][0], l[1][1]))
    return None

def excludeShadowRight(l, s):
    if l[0][1] < s[0][1]:
        return ((l[0][0], l[0][1]), (l[0][0], s[0][1]-1))
    return None

def driver_init():
    global driver
    driver = webdriver.Chrome()


def driver_quit():
    global driver
    driver.quit()


def driver_login():
    global driver

    driver.get('http://www.qlcoder.com/auth/login')
    time.sleep(1)
    driver.maximize_window()
    time.sleep(1)
    driver.find_element_by_xpath("//input[@id='email']").send_keys('mrujowfi@163.com')
    time.sleep(1)
    driver.find_element_by_xpath("//input[@id='password']").send_keys('kzchmwdi10')
    time.sleep(1)
    driver.find_element_by_xpath("//input[@id='login-submit']").click()
    time.sleep(3)


def driver_getQuestion():
    global driver

    driver.get('http://www.qlcoder.com/train/autocr')
    time.sleep(3)
    content = driver.find_element_by_xpath("//body").text
    if content.__contains__(u'请先登陆'):
        driver_login()
        return driver_getQuestion()
    else:
        question = content.split('\n')[6]  # mac
        print question.encode('utf-8')
        return question


def driver_sendAnswer(ans):
    global driver

    driver.get(ans)
    time.sleep(3)
    content = driver.find_element_by_xpath("//body").text
    if content.__contains__(u'请先登陆'):
        driver_login()
        driver_sendAnswer(ans)


if __name__ == '__main__':
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map, shadow, sum_walk, sum_second
    dev = True
    if dev is False:
        driver_init()
    try:
        if dev:
            timing.start()
            init('''
level=112&x=40&y=41&map=00010011110001100110000000000111001110001010000110001011000101111100000010000100010001100000010000100010011010000001001001111000000100111001000000000111000110110000000011100010010000110000111100100001001000010001100100100000001000001000010000110110000010011001010000010001000100001110000110000001110000100100001000000000111100101101110000001100100010000000111110000001010000001000111001110000000100010000001010001011000100000011100111000010000110010000110000001000010110000000100000100101111100001000010110100001100011010001100000000001000100001001000111010010001100000010001110001110110100101110010110010011110000100000011001101000001000101100100000000100011100010000000001000100000011100010001100010010000001000001100000000001010001000010001111111010011000011000010000110000000111110011110110000001110000001100001000000011100000100110000011001010001001110011100000011100001100000110000100011000100000000100000000000110000101111100100001000100111000110001100000101001100001010000100000011100101001000100000010000010001000000110111100011000100000010001000100110100000001111110011111001110000000001100000010001110000000100000011101100011111000100100010000000100000110000011110001111101000010000100000001100001001110000010000000100110001001100001000010000100000000100000011000011000001000001101101111110101110001110000011000000000001001010010001000001000011110000001011001000010100100001000010010100111000000110011001100000000010110111101000000000000000100011100001100000001000000100000000000100010110001111000100000111011000110111000000101001000111001111000000011001001110100001010100001000100000110010000110000001110010001000000111000000001
''')
            ans = start()
            sum_second += timing.stop(False)
            print '%s: %.2f mins, %d walks, avg: %.2f seconds' % (g_version, sum_second/float(60), sum_walk, sum_second*1.0/sum_walk)
        else:
            while True:
                timing.start()
                init(driver_getQuestion())
                ans = start()
                if ans is not None:
                    driver_sendAnswer(ans)
                sum_second += timing.stop(False)
                print '%s: %.2f mins, %d walks, avg: %.2f seconds' % (g_version, sum_second/float(60), sum_walk, sum_second*1.0/sum_walk)
    except Exception, e:
        timing.stop()
        print 'error', e
        print traceback.format_exc()
    if dev is False:
        driver_quit()

