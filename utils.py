import os

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.cuda.amp import autocast
from typing import Type, Any, Callable, Union, List, Optional
from torchvision.models import *
from tqdm import tqdm
from timeit import default_timer as timer
import math
import numpy as np

from tqdm import tqdm



'''
Retrieval utility methods.
'''
activation = {}
fwd_pass_x_list = []
fwd_pass_y_list = []

def get_activation(name):
	"""
	Get the activation from an intermediate point in the network.
	:param name: layer whose activation is to be returned
	:return: activation of layer
	"""
	def hook(model, input, output):
		activation[name] = output.detach()
	return hook


def append_feature_vector_to_list(activation, label):
	"""
	Append the feature vector to a list to later write to disk.
	:param activation: image feature vector from network
	:param label: ground truth label
	"""
	for i in range (activation.shape[0]):
		x = activation[i].cpu().detach().numpy()
		y = label[i].cpu().detach().numpy()
		fwd_pass_y_list.append(y)
		fwd_pass_x_list.append(x)


def dump_feature_vector_array_lists(config_name, output_path):
	"""
	Save the database and query vector array lists to disk.
	:param config_name: config to specify during file write
	:param output_path: path to dump database and query arrays after inference
	"""

	# save X (n x 2048), y (n x 1) to disk, where n = num_samples
	X_fwd_pass = np.asarray(fwd_pass_x_list, dtype=np.float32)
	y_fwd_pass = np.asarray(fwd_pass_y_list, dtype=np.float16).reshape(-1,1)

	np.save(output_path+'/'+str(config_name)+'-X.npy', X_fwd_pass)
	np.save(output_path+'/'+str(config_name)+'-y.npy', y_fwd_pass)


def generate_retrieval_data(model, emb_path, output_path,args):
	"""
	Iterate over data in dataloader, get feature vector from model inference, and save to array to dump to disk.
	:param model: ResNet50 model loaded from disk
	:param data_loader: loader for database or query set
	:param config: name of configuration for writing arrays to disk
	:param output_path: path to dump database and query arrays after inference
	"""
	model.eval()
	# model.avgpool.register_forward_hook(get_activation('avgpool'))
	if 'train_emb' in emb_path:
		mode = 'train'
	else:
		mode = 'val'

	img_path = os.path.join(emb_path,'img')
	label_path = os.path.join(emb_path,'label')

	assert img_path is not None

	dump_path = os.path.join(output_path, f'CSR_'+'topk_'+str(args.topk))
	if not os.path.exists(dump_path):
		os.makedirs(dump_path)
	with torch.no_grad():
		with autocast():
			# load from pretrained embedding
			for file in tqdm(os.listdir(img_path)):
				img_emb = torch.from_numpy(np.load(os.path.join(img_path, file)))
				target = torch.from_numpy(np.load(os.path.join(label_path, file)))
				_,_, feature, _, _= model(img_emb.cuda())
				append_feature_vector_to_list(feature, target.cuda())
			dump_feature_vector_array_lists(f'V1_{mode}_'+'topk_'+str(args.topk), dump_path)


	# re-initialize empty lists
	global fwd_pass_x_list
	global fwd_pass_y_list
	fwd_pass_x_list = []
	fwd_pass_y_list = []


def generate_pretrained_embed(model, data_loader, emb_path,):
	"""
	Iterate over data in dataloader, get feature vector from model inference, and save to array to dump to disk.
	:param model: ResNet50 model loaded from disk
	:param data_loader: loader for database or query set
	:param config: name of configuration for writing arrays to disk
	:param rep_size: representation size for fixed feature model
	:param output_path: path to dump database and query arrays after inference
	"""
	img_path = os.path.join(emb_path,'img')
	label_path = os.path.join(emb_path,'label')
	if not os.path.exists(img_path):
		os.makedirs(img_path)
	if not os.path.exists(label_path):
		os.makedirs(label_path)
	with torch.no_grad():
		with autocast():
			for i_batch, (images, target) in enumerate(tqdm(data_loader)):
				feature = model.forward_features(images.cuda())
				feature = model.forward_head(feature, pre_logits=True)
				# append_feature_vector_to_list(feature, target.cuda(), rep_size)
				img = feature.detach().cpu().numpy()
				'''save pretrained embedding '''
				np.save(f'{img_path}/emb_{i_batch}.npy', img)
				np.save(f'{label_path}/emb_{i_batch}.npy',target.detach().cpu().numpy())


	# re-initialize empty lists
	global fwd_pass_x_list
	global fwd_pass_y_list
	fwd_pass_x_list = []
	fwd_pass_y_list = []


