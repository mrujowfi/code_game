#coding=utf-8
import sys
import copy
import arg
import requests
import timing
import time
from selenium import webdriver
import traceback
import datetime

'''
气眼检测
波纹探测墙
波纹探测岛
探索顺序3,2,4,1
'''
global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map


def init(question):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map
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
    for each in temp_house:
        for each2 in each:
            print '%3d ' % each2,
        print ' '


#count one position value
def posCount(temp_house, i, j, temp_num_map, firstInit=False):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map

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
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map

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
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map

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
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map

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
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map

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
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map

    #origin_house at house_list[0]
    house_list.append((copy.deepcopy(house), copy.deepcopy(num_map)))
    #print travel(2, 2, 1)
    '''
    history = ''
    if travel(0, 1, 1):
        url = 'http://www.qlcoder.com/train/crcheck?x='+str(2+1)+'&y='+str(2+1)+'&path='+history
        print url
    '''
    print 'search 3'
    for i in range(line):
        for j in range(row):
            if house[i][j] == 3:
                #print '%d,%d\r' % (i, j),
                print 'walk', i, j
                history = ''
                if travel(i, j, 1):
                    url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+history
                    print url
                    return url
    timing.stop()

    print 'search 2'
    timing.start()
    del house_list[:]
    house_list = []
    house_list.append((copy.deepcopy(house), copy.deepcopy(num_map)))
    for i in range(line):
        for j in range(row):
            if house[i][j] == 2:
                #print '%d,%d\r' % (i, j),
                print 'walk', i, j
                history = ''
                if travel(i, j, 1):
                    url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+history
                    print url
                    return url
    timing.stop()

    print 'search 1,4'
    timing.start()
    del house_list[:]
    house_list = []
    house_list.append((copy.deepcopy(house), copy.deepcopy(num_map)))
    for i in range(line):
        for j in range(row):
            if house[i][j] == 4 or house[i][j] == 1:
                #print '%d,%d\r' % (i, j),
                print 'walk', i, j
                history = ''
                if travel(i, j, 1):
                    url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+history
                    print url
                    return url

    return None


#move from (pos_line, pos_row)
def travel(pos_line, pos_row, depth):
    global arg, line, row, house, house_list, start_line, start_row, history, failed_set, driver, num_map

    result = False
    a_house, a_num_map = house_list[depth-1]
    house_now = copy.deepcopy(a_house)
    num_map_now = copy.deepcopy(a_num_map)
    ok = areYouOK(house_now, pos_line, pos_row, num_map_now, depth)
    if ok==False:
        return False
    elif ok==True:
        return True
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
        if result:
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
        if result:
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
        if result:
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
        if result:
            return result

    return result


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
        return content.split('\n')[0]


def driver_sendAnswer(ans):
    global driver

    driver.get(ans)
    time.sleep(3)
    content = driver.find_element_by_xpath("//body").text
    if content.__contains__(u'请先登陆'):
        driver_login()
        driver_sendAnswer(ans)


if __name__ == '__main__':
    driver_init()
    try:
        if False:
            timing.start()
            init('''
level=79&x=29&y=30&map=001000100000011111000000011000000010001000000100011000000010000000011000100101110010001110111101110000100001000110100000001001000100001000001000100001000010000001100010101000010001011110100011001110000001000001001100001100011000110101100001100001000100001010010000001001001001110000100011000011101111000000000010010000100000001100011000001011000010100000011100011000100010001010011100000000011110001110000001000000000010000110000100000101111110000000110110010001000001110001100100000100000011011000000101110000000001101100011000001001000000111001101100100011101000000000001000100110001010000000100000000010000100011010010110111000011000000001001001000110000000000011111000001100001111000111110000001000111110000000010000100100000010000000110000100110100001011000100011110010010000001001010000101011000111000001000000010100100000010110000100000000000100000111110000110000
''')
            ans = start()
            timing.stop()
        else:
            while True:
                timing.start()
                init(driver_getQuestion())
                ans = start()
                if ans is not None:
                    driver_sendAnswer(ans)
                timing.stop()
    except Exception, e:
        timing.stop()
        print 'error', e
        print traceback.format_exc()
    driver_quit()

