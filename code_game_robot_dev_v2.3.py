#coding=utf-8
import sys
import timing
import time
from selenium import webdriver
import traceback
import datetime
import multiprocessing
import copy

g_version = 'v2.3'
'''
气眼检测 v1.0
波纹探测墙 v1.1
波纹探测岛 v2.0
探索顺序3,2,4,1 v2.1
初级残影检测 v2.2
改成进程类实现单机多进程 v2.3
'''

global driver


class ProcRobot(multiprocessing.Process):
    def __init__(self, dict_args):
        multiprocessing.Process.__init__(self)
        self.globalArgs = dict()
        self.arg = dict_args['arg']
        self.level = 0
        self.line = 0
        self.row = 0
        self.pos = 0
        self.house = 0
        self.house_list = 0
        self.history = 0
        self.num_map = 0
        self.shadow = 0
        self.sum_second = 0
        self.sum_walk = 0
        self.mission_type = int(dict_args['mission_type'])
        self.reverse = int(dict_args['reverse'])
        self.queue = dict_args['queue']
        self.data_lock = dict_args['data_lock']
        self.start_time = ''
        self.end_time = ''

    def run(self):
        print self.name+' start '
        try:
            self.init(self.arg)
            ans = self.robotStart(self.mission_type, self.reverse)
            if ans is not None:
                print '(%d, %d) is ok' % (self.mission_type, self.reverse)
                self.data_lock.acquire()
                self.queue.put(ans)
                self.data_lock.release()
                self.end_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S.%f")
                print 'lv:%s %s -> %s' % (self.level, self.start_time, self.end_time)
                print 'lv:%s (%d, %d) %s: %.2f mins, %d wa_lks, avg: %.2f seconds' % (self.level, self.mission_type, self.reverse, g_version, self.sum_second/float(60), self.sum_walk, self.sum_second*1.0/self.sum_walk)
        except Exception, e:
            print 'error', e
            time.sleep(1)
            print traceback.format_exc()
        print self.name+' stop '

    def init(self, question):
        self.arg = question.replace('\n', '')
        self.level = int(self.arg.split('&')[0].split('=')[1])
        self.line = int(self.arg.split('&')[1].split('=')[1])
        self.row = int(self.arg.split('&')[2].split('=')[1])
        self.pos = self.arg.split('&')[3].split('=')[1]
        self.house = [[0 for i in range(self.row)] for j in range(self.line)]
        self.house_list = []
        self.history = ''
        sys.setrecursionlimit(1000*self.line*self.row)
        self.num_map = {'num_-1': 0, 'num_0': 0, 'num_1': 0, 'num_2': 0, 'num_3': 0, 'num_4': 0}

        # each shadow position is (1, 1, 1, 1), means can start walking (up, down, left, right)
        self.shadow = [[[1 for k in range(4)] for i in range(self.row)] for j in range(self.line)]
        self.sum_second = 0
        self.sum_walk = 0

        #init each position
        for each in range(len(self.pos)):
            j = each%self.row
            i = (each-j)/self.row
            if self.pos[each] == '1':
                self.house[i][j] = -1
                self.num_map['num_-1'] += 1
            else:
                self.house[i][j] = 0

        #count position value
        for i in range(self.line):
            for j in range(self.row):
                if self.house[i][j] >= 0:
                    self.posCount(self.house, i, j, self.num_map, True)


        self.start_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S.%f")
        if self.mission_type == 3 and self.reverse == 0:
            print 'lv:%s start time: %s' % (self.level, self.start_time)
            print self.arg
            print self.line, self.row
            self.print_house(self.house)


    def print_house(self, temp_house):
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
    def posCount(self, temp_house, i, j, temp_num_map, firstInit=False):

        n = 0
        if i-1 >= 0 and temp_house[i-1][j] >= 0:
            n += 1
        if i+1 < self.line and temp_house[i+1][j] >= 0:
            n += 1
        if j-1 >= 0 and temp_house[i][j-1] >= 0:
            n += 1
        if j+1 < self.row and temp_house[i][j+1] >= 0:
            n += 1
        if not firstInit:
            temp_num_map['num_'+str(temp_house[i][j])] -= 1
        temp_num_map['num_'+str(n)] += 1
        temp_house[i][j] = n


    def multiArea(self, temp_house, block_line, block_row):

        #wave all blocks, and check if A-B==0 or A-B==2
        #wide is highest when travelling
        block_now = copy.deepcopy(temp_house)
        selected_list = []
        selected_list.append((block_line, block_row, 1))#(self.line, self.row, depth)
        search_wall = {'state': 0, 'cross': 0}

        #select all linked blocks
        #print 'block', block_line, block_row
        #print_house(block_now)
        try:
            block_now[block_line][block_row] = -2
            if block_line == 0 or block_line == self.line-1 or block_row == 0 or block_row == self.row-1:
                search_wall['wall-2'] = 1
            result = self.travelBlock(block_now, selected_list, search_wall)
        except RuntimeError, e:
            print 'error', e
            result = False

        #analyse wall to wall
        if not result:
            result = self.analyzeMulti(block_now)
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


    def travelBlock(self, block_now, selected_list, search_wall):

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
        if i+1 < self.line:
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
        if j+1 < self.row:
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
        if i+1 < self.line and j > 0 and block_now[i+1][j-1] == -1:
            #down,left
            block_now[i+1][j-1] = -1 - (depth+1)
            selected_list.append((i+1, j-1, depth+1))
        if i > 0 and j+1 < self.row and block_now[i-1][j+1] == -1:
            #up,right
            block_now[i-1][j+1] = -1 - (depth+1)
            selected_list.append((i-1, j+1, depth+1))
        if i+1 < self.line and j+1 < self.row and block_now[i+1][j+1] == -1:
            #down,right
            block_now[i+1][j+1] = -1 - (depth+1)
            selected_list.append((i+1, j+1, depth+1))

        #mark this wave if wall
        if i == 0 or i == self.line-1 or j == 0 or j == self.row-1:
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

        return self.travelBlock(block_now, selected_list, search_wall)


    def analyzeMulti(self, block_now):

        target = 0
        searching = True
        if block_now[0][0] < -1:
            #selected
            for j in range(self.row):
                if searching:
                    if block_now[0][j] >= -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[0][j] < -1:
                        searching = True
            for i in range(self.line):
                if searching:
                    if block_now[i][self.row-1] >= -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[i][self.row-1] < -1:
                        searching = True
            for j in range(self.row-1, -1, -1):
                if searching:
                    if block_now[self.line-1][j] >= -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[self.line-1][j] < -1:
                        searching = True
            for i in range(self.line-1, -1, -1):
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
            for j in range(self.row):
                if searching:
                    if block_now[0][j] < -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[0][j] >= -1:
                        searching = True
            for i in range(self.line):
                if searching:
                    if block_now[i][self.row-1] < -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[i][self.row-1] >= -1:
                        searching = True
            for j in range(self.row-1, -1, -1):
                if searching:
                    if block_now[self.line-1][j] < -1:
                        target += 1
                        if target == 2:
                            return True
                        searching = False
                else:
                    if block_now[self.line-1][j] >= -1:
                        searching = True
            for i in range(self.line-1, -1, -1):
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


    def areYouOK(self, temp_house, block_line, block_row, temp_num_map, depth):

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
        #if num_1*4>self.line*self.row and num_1*2<self.line*self.row and block_line!=None and block_row!=None and multiArea(temp_house, block_line, block_row):
        #    return False
        if depth % 3 == 0:
            if self.multiArea(temp_house, block_line, block_row):
                return False
            self.data_lock.acquire()
            queue_size = self.queue.qsize()
            self.data_lock.release()
            if queue_size == 1:
                return False

        #possibly
        return None


    def robotStart(self, mission_type, reverse):

        #origin_house at self.house_list[0]

        #print travel(2, 2, 1)
        '''
        self.house_list.append((copy.deepcopy(self.house), copy.deepcopy(self.num_map)))
        self.history = ''
        i = 30
        j = 6
        result = travel_first(i, j, 1)
        if result[0]:
            url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+self.history
            print url
        '''
        # print 'search '+str(mission_type)+' '+str(reverse)
        timing.start()
        self.house_list.append((copy.deepcopy(self.house), copy.deepcopy(self.num_map)))
        i_range = range(self.line)
        j_range = range(self.row)
        if reverse == 1:
            i_range.reverse()
            j_range.reverse()
        for i in i_range:
            for j in j_range:
                self.data_lock.acquire()
                queue_size = self.queue.qsize()
                self.data_lock.release()
                if self.house[i][j] == int(mission_type) and queue_size == 0:
                    self.sum_walk += 1
                    # print '%d,%d\r' % (i, j),
                    print '(%d, %d) walk %d %d' % (self.mission_type, self.reverse, i, j)
                    self.history = ''
                    result = self.travel_first(i, j, 1)
                    if result[0]:
                        url = 'http://www.qlcoder.com/train/crcheck?x='+str(i+1)+'&y='+str(j+1)+'&path='+self.history
                        print url
                        self.sum_second += timing.stop()
                        return url
        self.sum_second += timing.stop()

        return None


    #move from (pos_line, pos_row)
    #return (result, (ul, ur, dl, dr))
    def travel_first(self, pos_line, pos_row, depth):

        result = (False, ((0, 0), (0, 0)))
        a_house, a_num_map = self.house_list[depth-1]
        house_now = copy.deepcopy(a_house)
        num_map_now = copy.deepcopy(a_num_map)
        this_shadow_line = [0, 0, 0, 0]#for up, down, left, right count


        #print pos_line, pos_row
        #print_house(house_now)
        #move up
        #if self.shadow[pos_line][pos_row][0] == 0:
        #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 0)
        if self.shadow[pos_line][pos_row][0] == 1 and pos_line-1 >= 0 and house_now[pos_line-1][pos_row] >= 0:
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
            for i in range(pos_line-inc if pos_line-inc>=0 else 0, (pos_line+2) if pos_line+1<self.line else self.line):
                for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<self.row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<self.row else [pos_row,]:
                    if house_up[i][j] >= 0:
                        self.posCount(house_up, i, j, num_map_up)
                        if house_up[i][j] == 0 or house_up[i][j] == 1:
                            no_shadow = True
            self.history = self.history[:depth-1]+'u'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_up)
            self.house_list = self.house_list[:depth]+[(house_up,num_map_up),]
            result = self.travel(pos_line-(inc-1), pos_row, depth+1)
            shadow_line_excluded = self.excludeShadowUp(((pos_line-this_shadow_line[0], pos_row), (pos_line, pos_row)), result[1])
            #print result[1], shadow_line_excluded
            if no_shadow is False and shadow_line_excluded is not None:
                for step in range(shadow_line_excluded[0][0], shadow_line_excluded[1][0]+1):
                    self.shadow[step][pos_row][0] = 0
            if result[0]:
                return result

        #move down
        #if self.shadow[pos_line][pos_row][1] == 0:
        #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 1)
        if self.shadow[pos_line][pos_row][1] == 1 and pos_line+1 < self.line and house_now[pos_line+1][pos_row] >= 0:
            no_shadow = False#flag for not use shadow because eye analyse
            house_down = copy.deepcopy(house_now)
            num_map_down = copy.deepcopy(num_map_now)
            inc = 1
            while pos_line+inc < self.line and house_down[pos_line+inc][pos_row] >= 0:
                num_map_down['num_'+str(house_down[pos_line+(inc-1)][pos_row])] -= 1
                num_map_down['num_'+str(-1)] += 1
                house_down[pos_line+(inc-1)][pos_row] = -1
                this_shadow_line[1] += 1
                inc+=1
            #recount value
            for i in range(pos_line-1 if pos_line-1>=0 else 0, (pos_line+inc) if pos_line+inc<self.line else self.line):
                for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<self.row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<self.row else [pos_row,]:
                    if house_down[i][j] >= 0:
                        self.posCount(house_down, i, j, num_map_down)
                        if house_down[i][j] == 0 or house_down[i][j] == 1:
                            no_shadow = True
            self.history = self.history[:depth-1]+'d'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_down)
            self.house_list = self.house_list[:depth]+[(house_down,num_map_down),]
            result = self.travel(pos_line+(inc-1), pos_row, depth+1)
            shadow_line_excluded = self.excludeShadowDown(((pos_line, pos_row), (pos_line+this_shadow_line[1], pos_row)), result[1])
            #print result[1], shadow_line_excluded
            if no_shadow is False and shadow_line_excluded is not None:
                for step in range(shadow_line_excluded[0][0], shadow_line_excluded[1][0]+1):
                    #if step == '31' and pos_row == 6:
                    #print 'close', pos_line, pos_row, step, pos_row, this_shadow_line, shadow_line_excluded
                    self.shadow[step][pos_row][1] = 0
            if result[0]:
                return result

        #move left
        #if self.shadow[pos_line][pos_row][2] == 0:
        #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 2)
        if self.shadow[pos_line][pos_row][2] == 1 and pos_row-1 >= 0 and house_now[pos_line][pos_row-1] >= 0:
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
            for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<self.line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<self.line else [pos_line,]:
                for j in range(pos_row-inc if pos_row-inc>=0 else 0, (pos_row+2) if pos_row+1<self.row else self.row):
                    if house_left[i][j] >= 0:
                        self.posCount(house_left, i, j, num_map_left)
                        if house_left[i][j] == 0 or house_left[i][j] == 1:
                            no_shadow = True
            self.history = self.history[:depth-1]+'l'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_left)
            self.house_list = self.house_list[:depth]+[(house_left,num_map_left),]
            result = self.travel(pos_line, pos_row-(inc-1), depth+1)
            shadow_line_excluded = self.excludeShadowLeft(((pos_line, pos_row-this_shadow_line[2]), (pos_line, pos_row)), result[1])
            #print result[1], shadow_line_excluded
            if no_shadow is False and shadow_line_excluded is not None:
                for step in range(shadow_line_excluded[0][1], shadow_line_excluded[1][1]+1):
                    self.shadow[pos_line][step][2] = 0
            if result[0]:
                return result

        #move right
        #if self.shadow[pos_line][pos_row][3] == 0:
        #    print 'shadow (%d, %d) %d' % (pos_line, pos_row, 3)
        if self.shadow[pos_line][pos_row][3] == 1 and pos_row+1 < self.row and house_now[pos_line][pos_row+1] >= 0:
            no_shadow = False#flag for not use shadow because eye analyse
            house_right = copy.deepcopy(house_now)
            num_map_right = copy.deepcopy(num_map_now)
            inc = 1
            while pos_row+inc < self.row and house_right[pos_line][pos_row+inc] >= 0:
                num_map_right['num_'+str(house_right[pos_line][pos_row+(inc-1)])] -= 1
                num_map_right['num_'+str(-1)] += 1
                house_right[pos_line][pos_row+(inc-1)] = -1
                this_shadow_line[3] += 1
                inc+=1
            #recount value
            for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<self.line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<self.line else [pos_line,]:
                for j in range(pos_row-1 if pos_row-1>0 else 0, (pos_row+inc) if pos_row+inc<self.row else self.row):
                    if house_right[i][j] >= 0:
                        self.posCount(house_right, i, j, num_map_right)
                        if house_right[i][j] == 0 or house_right[i][j] == 1:
                            no_shadow = True
            self.history = self.history[:depth-1]+'r'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_right)
            self.house_list = self.house_list[:depth]+[(house_right,num_map_right),]
            result = self.travel(pos_line, pos_row+(inc-1), depth+1)
            shadow_line_excluded = self.excludeShadowRight(((pos_line, pos_row), (pos_line, pos_row+this_shadow_line[3])), result[1])
            #print result[1], shadow_line_excluded
            if no_shadow is False and shadow_line_excluded is not None:
                for step in range(shadow_line_excluded[0][1], shadow_line_excluded[1][1]+1):
                    self.shadow[pos_line][step][3] = 0
            if result[0]:
                return result

        return result


    #move from (pos_line, pos_row)
    #return (result, (ul, dr))
    def travel(self, pos_line, pos_row, depth):

        result = (False, ((0, 0), (0, 0)))
        this_shadow = ((pos_line, pos_row), (pos_line, pos_row))#ul, dr
        #this_shadow_line = {'ul': {'line': pos_line, 'row': pos_row}, 'dr': {'line': pos_line, 'row': pos_row}}#ul, dr
        this_shadow_line = [0, 0, 0, 0]#for up, down, left, right count
        a_house, a_num_map = self.house_list[depth-1]
        house_now = copy.deepcopy(a_house)
        num_map_now = copy.deepcopy(a_num_map)
        ok = self.areYouOK(house_now, pos_line, pos_row, num_map_now, depth)
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
            for i in range(pos_line-inc if pos_line-inc>=0 else 0, (pos_line+2) if pos_line+1<self.line else self.line):
                for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<self.row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<self.row else [pos_row,]:
                    if house_up[i][j] >= 0:
                        self.posCount(house_up, i, j, num_map_up)
            self.history = self.history[:depth-1]+'u'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_up)
            self.house_list = self.house_list[:depth]+[(house_up,num_map_up),]
            result = self.travel(pos_line-(inc-1), pos_row, depth+1)
            this_shadow = self.mergeShadow(self.mergeShadow(((pos_line - this_shadow_line[0], pos_row), (pos_line, pos_row)), result[1]), this_shadow)
            #if depth == 2:
            #    print 'lgbu', pos_line, pos_row, this_shadow
            if result[0]:
                result = (True, this_shadow)
                return result

        #move down
        if pos_line+1 < self.line and house_now[pos_line+1][pos_row] >= 0:
            house_down = copy.deepcopy(house_now)
            num_map_down = copy.deepcopy(num_map_now)
            inc = 1
            while pos_line+inc < self.line and house_down[pos_line+inc][pos_row] >= 0:
                num_map_down['num_'+str(house_down[pos_line+(inc-1)][pos_row])] -= 1
                num_map_down['num_'+str(-1)] += 1
                house_down[pos_line+(inc-1)][pos_row] = -1
                this_shadow_line[1] += 1
                inc+=1
            #recount value
            for i in range(pos_line-1 if pos_line-1>=0 else 0, (pos_line+inc) if pos_line+inc<self.line else self.line):
                for j in [pos_row-1, pos_row, pos_row+1] if pos_row-1>=0 and pos_row+1<self.row else [pos_row-1, pos_row] if pos_row-1>0 else [pos_row, pos_row+1] if pos_row+1<self.row else [pos_row,]:
                    if house_down[i][j] >= 0:
                        self.posCount(house_down, i, j, num_map_down)
            self.history = self.history[:depth-1]+'d'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_down)
            self.house_list = self.house_list[:depth]+[(house_down,num_map_down),]
            result = self.travel(pos_line+(inc-1), pos_row, depth+1)
            this_shadow = self.mergeShadow(self.mergeShadow(((pos_line, pos_row), (pos_line + this_shadow_line[1], pos_row)), result[1]), this_shadow)
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
            for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<self.line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<self.line else [pos_line,]:
                for j in range(pos_row-inc if pos_row-inc>=0 else 0, (pos_row+2) if pos_row+1<self.row else self.row):
                    if house_left[i][j] >= 0:
                        self.posCount(house_left, i, j, num_map_left)
            self.history = self.history[:depth-1]+'l'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_left)
            self.house_list = self.house_list[:depth]+[(house_left,num_map_left),]
            result = self.travel(pos_line, pos_row-(inc-1), depth+1)
            this_shadow = self.mergeShadow(self.mergeShadow(((pos_line, pos_row - this_shadow_line[2]), (pos_line, pos_row)), result[1]), this_shadow)
            #if depth == 2:
            #    print 'lgbl', pos_line, pos_row, depth, this_shadow, result[1]
            if result[0]:
                result = (True, this_shadow)
                return result

        #move right
        if pos_row+1 < self.row and house_now[pos_line][pos_row+1] >= 0:
            house_right = copy.deepcopy(house_now)
            num_map_right = copy.deepcopy(num_map_now)
            inc = 1
            while pos_row+inc < self.row and house_right[pos_line][pos_row+inc] >= 0:
                num_map_right['num_'+str(house_right[pos_line][pos_row+(inc-1)])] -= 1
                num_map_right['num_'+str(-1)] += 1
                house_right[pos_line][pos_row+(inc-1)] = -1
                this_shadow_line[3] += 1
                inc+=1
            #recount value
            for i in [pos_line-1, pos_line, pos_line+1] if pos_line-1>=0 and pos_line+1<self.line else [pos_line-1, pos_line] if pos_line-1>0 else [pos_line, pos_line+1] if pos_line+1<self.line else [pos_line,]:
                for j in range(pos_row-1 if pos_row-1>0 else 0, (pos_row+inc) if pos_row+inc<self.row else self.row):
                    if house_right[i][j] >= 0:
                        self.posCount(house_right, i, j, num_map_right)
            self.history = self.history[:depth-1]+'r'
            if depth % 100 == 0:
                #print self.history
                pass
            #print_house(house_right)
            self.house_list = self.house_list[:depth]+[(house_right,num_map_right),]
            result = self.travel(pos_line, pos_row+(inc-1), depth+1)
            this_shadow = self.mergeShadow(self.mergeShadow(((pos_line, pos_row), (pos_line, pos_row - this_shadow_line[3])), result[1]), this_shadow)
            #if depth == 2:
            #    print 'lgbr', pos_line, pos_row, depth, this_shadow, result[1]
            if result[0]:
                result = (True, this_shadow)
                return result

        result = (False, this_shadow)
        return result

    def mergeShadow(self, sa, sb):
        sr = ((sa[0][0] if sa[0][0]<sb[0][0] else sb[0][0], sa[0][1] if sa[0][1]<sb[0][1] else sb[0][1]), (sa[1][0] if sa[1][0]>sb[1][0] else sb[1][0], sa[1][1] if sa[1][1]>sb[1][1] else sb[1][1]))
        return sr

    def excludeShadowUp(self, l, s):
        if l[1][0] > s[1][0]:
            return ((s[1][0]+1, l[1][1]), (l[1][0], l[1][1]))
        return None

    def excludeShadowDown(self, l, s):
        if l[0][0] < s[0][0]:
            return ((l[0][0], l[0][1]), (s[0][0]-1, l[0][1]))
        return None

    def excludeShadowLeft(self, l, s):
        if l[1][1] > s[1][1]:
            return ((l[1][0], s[1][1]+1), (l[1][0], l[1][1]))
        return None

    def excludeShadowRight(self, l, s):
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

    content = ''
    while content == '':
        time.sleep(1)
        print 'wait for page'
        content = driver.find_element_by_xpath("//body").text

    if content.__contains__(u'请先登陆'):
        driver_login()
        return driver_getQuestion()
    else:
        question = content.split('\n')[7]
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
    dev = True
    if dev is False:
        driver_init()
    try:
        if dev:
            dict_args = {}
            dict_args['queue'] = multiprocessing.Queue(maxsize=5)
            dict_args['data_lock'] = multiprocessing.RLock()
            dict_args['arg'] = '''
level=133&x=47&y=48&map=001000001000000010011111111100111111000100000000001011100010000010000000000100001111000100000010000011110000000010001110000101000001001100111000000110000101000010001110001001010101000100110001011000100100010000100000000010000100010100000100010011000110011100000001000000100000110001000110010111000110011000011100001100000011111000010000000000111111111011111110000001111001100011111111101000111111001000110000110000000001000000000000001011111111001110110001000000001101010100000000000011000011000010001100010000001001010000000001110000010010011000001000000000011000000011110001110001110100100001111010001000010010001000010111100100000001000110000000101000110000100001000111101100001011010010000100000010110110110100011111101000101000000011000001000110000110110100000000100010000000101000010011110001110010000100001110001100010000001010010001000100100011000000001100000001110011000011100100010110001001011000100001000111111000000010001100000000000100010010000011000111001001000010000000000011110111110000010000000111001001000100000010000000100110000001010110000100001111110101111110100010001110111111000100000000100110000100010000001000001000111000100001111010110010000111000011000000001010001010100111100010100011000000001000110000001000100000110000101000100000001000110000100111100000111101111000100000001111100010000100001100000000110001001000000100001100010011100001100000010001000100001000000100000001000111111000000010000101000000001000001001000100000000001111000010001100011110001111001000010000000010000011000000100111010000001001000010000110000010010001000100000100000100000001011110001110000001000101010001110000100000000100001110000000111100001100010011000000101011110110101000011100000010001100001001000000001001000000001001110001011000100000100101111111001100011011000001100001000110001010110001001110001110011000111100001001110000010010000111000010101100000000110001001000100001010111100100010010000001001100000100001010001000010011101100000100011000110000000011000011000010000010001100001101100010000010111000010000011110001000111000000001000011101000000110000111111000001000100010000000010011100001010010000011000010001000100100111110000000110001001000001000010000100000110100000000101110000100100000000000000100111100110000000010001110010000
'''
            #create processes
            processed = []
            for i in [3, 4, 2, 1]:
                dict_args['mission_type'] = i
                dict_args['reverse'] = 0
                processed.append(ProcRobot(dict_args))
                dict_args['reverse'] = 1
                processed.append(ProcRobot(dict_args))

            #start processes
            for i in range(len(processed)):
                processed[i].start()
                time.sleep(1)

            #join processes
            for i in range(len(processed)):
                processed[i].join()

            dict_args['data_lock'].acquire()
            if dict_args['queue'].qsize() == 1:
                ans = dict_args['queue'].get()
                print 'driver_sendAnswer(ans)'
            else:
                print 'all failed'
            dict_args['data_lock'].release()
        else:
            while True:
                dict_args = {}
                dict_args['queue'] = multiprocessing.Queue(maxsize=5)
                dict_args['data_lock'] = multiprocessing.RLock()
                dict_args['arg'] = driver_getQuestion()
                #create processes
                processed = []
                for i in [3, 4, 2, 1]:
                    dict_args['mission_type'] = i
                    dict_args['reverse'] = 0
                    processed.append(ProcRobot(dict_args))
                    dict_args['reverse'] = 1
                    processed.append(ProcRobot(dict_args))

                #start processes
                for i in range(len(processed)):
                    processed[i].start()
                    time.sleep(1)

                #join processes
                for i in range(len(processed)):
                    processed[i].join()

                dict_args['data_lock'].acquire()
                if dict_args['queue'].qsize() == 1:
                    ans = dict_args['queue'].get()
                    driver_sendAnswer(ans)
                else:
                    print 'all failed'
                dict_args['data_lock'].release()

    except Exception, e:
        print 'error', e
        time.sleep(1)
        print traceback.format_exc()
    if dev is False:
        driver_quit()
