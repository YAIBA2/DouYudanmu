#coding:utf-8
import socket,re,time,threading,urllib.request,json,urllib.parse,random,sys
#运行方式：将url修改为指定的直播间地址，python3命令行直接执行即可
class Danmu(object):#danmu主体类
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   #初始的socket连接
        self.C2S = 689 #douyu协议消息类型客户端发往服务器标志
        self.S2C = 690#服务器发往客户端标志号
        self.gid = -9999#组号
        self.rid = 6324#默认房间号

    def log(self,str):#数据记录与屏幕输出
        now_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        log = now_time + '\t\t' + str
        with open(sys.path[0]+'\log.txt','a',encoding='utf-8')as f:
            f.writelines(log + '\n')
        print(log)
        
    def sendMsg(self,msg):#发包函数，传入包内容
            msg = msg.encode('utf-8')
            data_length= len(msg)+8
            msgHead=int.to_bytes(data_length,4,'little')+int.to_bytes(data_length,4,'little')+int.to_bytes(self.C2S,4,'little')#构造斗鱼协议的消息头
            self.sock.sendall(msgHead+msg)

    def keeplive(self):#心跳包维持
        while True:
            msg='type@=keeplive/tick@='+str(int(time.time()))+'/\x00'#心跳包构造
            self.sendMsg(msg)
            time.sleep(45)#45s心跳包间隔

    def getInfo(self,url):#分析网页中的信息
        self.log("请求网页内容...")
        try:
            with urllib.request.urlopen(url)as f:#urllib访问网页，返回网页 源文件
                data = f.read().decode()
        except BaseException as e:
            self.log("请求网页内容失败...")
            exit(1)
        self.log("获取房间信息...")
        room = re.search('var \$ROOM = (.*);',data)#从js中提取￥ROOM变量，并用json进行解析
        if room:
            room = room.group(1)
            room = json.loads(room)
            self.log("房间名:"+room["room_name"]+'\t主播:'+room["owner_name"])
            self.rid = room["room_id"]
            if room["show_status"] == 2:
                self.log("未开播!\t\t"+str(self.rid))#若直播间未开播直接退出
                exit(1)



    def connectToDanMuServer(self):#连接弹幕服务器
        HOST = 'openbarrage.douyutv.com'#弹幕服务器地址
        PORT = 8601#弹幕服务器端口

        self.log("连接弹幕服务器..."+HOST+':'+str(PORT))
        self.sock.connect((HOST, PORT))#socket进行连接
        self.log("连接成功,发送登录请求...")
        msg = 'type@=loginreq/username@=/password@=/roomid@='+str(self.rid)+'/\x00'#登陆请求
        self.sendMsg(msg)
        data = self.sock.recv(1024)
        #self.log('Received from login\t\t'+ repr(data))
        a = re.search(b'type@=(\w*)', data)
        if a.group(1)!=b'loginres':#根据接受type为loginges进行判断，若不是证明登录失败
            self.log("登录失败,程序退出...")
            exit(0)
        self.log("登录成功")

        msg = 'type@=joingroup/rid@='+str(self.rid)+'/gid@=-9999/\x00'#入组请求
        self.sendMsg(msg)
        self.log("进入弹幕服务器...")
        threading.Thread(target=Danmu.keeplive,args=(self,)).start()#创建心跳包维持线程
        self.log("心跳包机制启动...")
        data = self.sock.recv(1024)
        #print('Received', repr(data))




    def danmuClassify(self):#弹幕信息进行分类
        self.log("监听中")
        while True:#循环监听弹幕
            try:
                chatmsgLst=self.sock.recv(2048).split(b'\xb2\x02\x00\x00')#通过消息类型字段将数据流分段
            except ConnectionAbortedError as e:
                print(e)
            for chatmsg in chatmsgLst[1:]:#跳过第一段tcp头信息，从第二段以此处理
                typeContent = re.search(b'type@=(.*?)/',chatmsg)#获取type类型
                try:
                    if typeContent.group(1)==b'chatmsg':#若是弹幕信息
                        try:
                            contentMsg=(b''.join(re.findall(b'txt@=(.*?)/',chatmsg)).decode('utf-8','ignore'))#弹幕内容
                            snickMsg=(b''.join(re.findall(b'nn@=(.*?)/',chatmsg)).decode('utf-8','ignore'))#昵称
                            level=(b''.join(re.findall(b'level@=(.*?)/',chatmsg)).decode())#等级
                            strprint = '[Lv'+level+']'+snickMsg+':'+contentMsg
                            self.log(strprint)
                        except BaseException as e:
                            self.log("\t\t_________解析弹幕信息失败:"+str(chatmsg))
                            print(e)
                    if typeContent.group(1)==b'uenter':#若是进入直播间欢迎信息
                        try:
                            snickMsg=(b''.join(re.findall(b'nn@=(.*?)/',chatmsg)).decode('utf-8','ignore'))
                            level=(b''.join(re.findall(b'level@=(.*?)/',chatmsg)).decode())
                            strprint = '欢迎'+'[Lv'+level+']'+snickMsg+'来到本直播间'
                            self.log(strprint)
                        except BaseException as e:
                            self.log("\t\t_________解析弹幕信息失败:"+str(chatmsg))
                            print(e)
                    if typeContent.group(1)==b'dgb':#若是礼物信息
                        try:
                            snickMsg=(b''.join(re.findall(b'nn@=(.*?)/',chatmsg)).decode('utf-8','ignore'))
                            level=(b''.join(re.findall(b'level@=(.*?)/',chatmsg)).decode())
                            gift=(b''.join(re.findall(b'gfid@=(.*?)/',chatmsg)).decode())#礼物类型
                            hit=(b''.join(re.findall(b'hits@=(.*?)/',chatmsg)).decode())#连击次数
                            if gift in ['50','56','191']:
                                if not hit:
                                    strprint = '[Lv'+level+']'+snickMsg+':赠送给主播[100鱼丸]'+'[1]连击'
                                else:
                                    strprint = '[Lv'+level+']'+snickMsg+':赠送给主播[100鱼丸]'+'['+hit+']连击'
                            if gift in ['57','192']:
                                if not hit:
                                    strprint = '[Lv'+level+']'+snickMsg+':赠送给主播[赞]'+'[1]连击'
                                else:
                                    strprint = '[Lv'+level+']'+snickMsg+':赠送给主播[赞]'+'['+hit+']连击'
                            if gift in ['58','193']:
                                if not hit:
                                    strprint = '[Lv'+level+']'+snickMsg+':赠送给主播[弱鸡]'+'[1]连击'
                                else:
                                    strprint = '[Lv'+level+']'+snickMsg+':赠送给主播[弱鸡]'+'['+hit+']连击'
                            if gift in ['59','194']:
                                if not hit:
                                    strprint = '[Lv'+level+']'+snickMsg+':赠送给主播[666]'+'[1]连击'
                                else:
                                    strprint = '[Lv'+level+']'+snickMsg+':赠送给主播[666]'+'['+hit+']连击'
                            if strprint.split():
                                self.log(strprint)
                        except BaseException as e:
                            self.log("\t\t_________解析弹幕信息失败:"+str(chatmsg))
                            print(e)
                except BaseException as e:
                        self.log("\t\t_________解析弹幕信息失败:"+str(chatmsg))
                        print(e)
if __name__ == '__main__':
    url = 'http://www.douyu.com/wt55kai'#直播间url
    danmu = Danmu()
    danmu.getInfo(url)
    danmu.connectToDanMuServer()
    danmu.danmuClassify()
