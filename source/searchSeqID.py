import json
import requests
from bs4 import BeautifulSoup
from queue import Queue
from threading import Thread
import numpy as np


### ip池
def get_ip_list():
	"""
		获取代理ip池
	"""
	url = "https://www.xicidaili.com/wt"
	headers = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Safari/537.36'}
	res = requests.get(url, headers=headers)
	html = res.content.decode()
	# print(html)
	soup = BeautifulSoup(html, 'html.parser')
	trs = soup.find_all('tr')[1:]
	ip_list = []
	for tr in trs:
		tds = [td.text for td in tr.find_all('td')]
		ip_addr = tds[1]
		port = tds[2]
		ip_type = tds[5]
		ip_list.append("%s://%s:%s" %(ip_type, ip_addr, port))
	return ip_list


def random_choose_ip(ip_list):
	"""
		从代理ip池中随机选择ip
	"""
	ip = np.random.choice(ip_list)
	return ip


def searchSeqID(seq):
	"""
		POST 数据并获得搜索结果
	"""
	sess = requests.Session()
	headers = {
		"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36"
	}
	sess.headers.update(headers)

	ip = random_choose_ip(ip_list)
	proxies = {
		ip.split(':')[0]:ip,
	}
	data = {
		'printParams': 'no',
		'fromDB': 'no',
		'sequence_file': '(binary)',
		'sequence': "%s" %(seq),
		'strain': 'both',
		'source': 'isolates',
		'size': 'gt1200',
		'quality': 'good',
		'taxonomy': 'rdpHome',
		'num': 20,
		'submit': 'Submit',
	}
	url = "http://rdp.cme.msu.edu/seqmatch/SeqmatchControllerServlet/start"
	res = sess.post(url, data=data, proxies=proxies)
	print("已发送数据", res)
	res = sess.get('http://rdp.cme.msu.edu/seqmatch/seqmatch_result.jsp?qvector=204&depth=0&currentRoot=0&num=20',
				    proxies=proxies)
	html = res.text
	print("已获取序列比对数据", res)
	with open('./test_page.html', 'w') as f:
		f.write(html)
	
	# 搜索 match_score 大于等于0.95的序列id
	soup = BeautifulSoup(html, 'html.parser')
	detail_html = soup.find('div', {'class':'details'})
	seq_id_list = [item.text for item in detail_html.find_all('a', {'target':'_blank'})]
	match_score = np.array([float(item.text) for item in detail_html.find_all('span', {'style':'background-color: #FFDBB8'})[1:]])
		
	seq_id_searched = []
	if True not in (match_score >= 0.95):
		print('match_score 全部小于0.95')
	for i, score in enumerate(match_score):
		if score >= 0.95:
			seq_id_searched.append(seq_id_list[i])
	
	return seq_id_searched


def searchBatchSeqID(strain_name, fasta_list, queue):
	"""
		多线程爬虫的批次任务
	"""
	batch_data = [strain_name, []]
	for i, seq in enumerate(fasta_list):
		print("%d " %(i+1), end='')
		try:
			batch_data[1].extend(searchSeqID(seq))
		except:
			batch_data[1].extend([])
	queue.put(batch_data)
	print("成功获取 %s 的所有 seq_id" %(strain_name))


def searchAllSeqID(fasta_need_search):
	"""
		多线程爬虫获取全部菌属的匹配的 seq_id
	"""
	queue = Queue()
	thds = []
	for strain_name, fasta_list in fasta_need_search.items():
		thd = Thread(target=searchBatchSeqID,
					args=(strain_name, fasta_list, queue))
		thd.start()
		thds.append(thd)
		print("开启 %s 的线程" %(strain_name))
	for thd in thds:
		thd.join()
		
	seq_id_searched = []
	for thd in thds:
		seq_id_searched.append(queue.get())
	print('成功获取所有seq_id')
	return seq_id_searched


def main(folder):
	# 读取 fasta_need_search.json 并获得需要搜索的菌属名与序列信息
	fpath = './dataset/%s/fasta_need_search.json' %(folder)
	fasta_need_search = json.loads(open(fpath).read())
	
	# A test
	fasta = {"k__Bacteria;p__Proteobacteria;c__Alphaproteobacteria;o__Rhodobacterales;f__Rhodobacteraceae;Other": 
	["TACGGAGGgggTTAGCGTTGTTCGGAATTACTGGGCGTAAAGCgcgcgTAGGCGGACTAGTCAGTCAGAGGTGAAATCCCAGGGCTCAACCCTGGAACTGCCTTTGATACTGCTGGTCTTGAGTTCGAgagagGTGAGTGGAATTCCGAGTGTAGAGGTGAAATTCGTAGATATTCGGAGGAACACCAGTGGCGAAGGCGGCTCACTGGCTCGATACTGACGCTGAGGTGCGAAAGCGTGGGGAGCAAACAGGATTAGATACCCTGGTAGTCCACGCCGTAAACGATGAATGCCAGTCGTCGGGCAGTATACTGTTCGGTGACacacCTAACGGATTAAGCATTCCGCCTG",
	 "TACGGAGGgggCTAGCGTTGTTCGGAATTACTGGGCGTAAAGCGCACGTAGGCGGACTATTAAGTCAGGGGTGAAATCCCGGGGCTCAACCCCGGAACTGCCTTTGATACTGGTAGTCTAGAGTTCGAgagagGTGAGTGGAACTCCGAGTGTAGAGGTGAAATTCGTAGATATTCGGAAGAACACCAGTGGCGAAGGCGGCTCACTGGCTCGATACTGACGCTGAGGTGCGAAAGCGTGGGGAGCAAACAGGATTAGATACCCTGGTAGTCCACGCCGTAAACGATGAATGCCAGACGTCGGCAAGCATGCTTGTCGGTGTCACACCTAACGATTAAGCATTCCGGCCTGGGGAGTACGGTCGCAAGATTA"]}
	seq_id_searched = searchAllSeqID(fasta)
	
	# seq_id_searched = searchAllSeqID(fasta_need_search)
	with open('./dataset/%s/seq_id_searched.txt' %(folder), 'w') as f:
		f.write(str(seq_id_searched))
	f.close()


if __name__=="__main__":
	ip_list = get_ip_list()
	main(input("请输入数据集名: "))
