from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from __future__ import print_function

import torch as th
from torch.utils.data import Dataset
import pickle
import torch.nn.functional as F
import numpy as np
import re
from collections import defaultdict
from torch.utils.data.dataloader import default_collate

import os
import pandas as pd

class Epic_DataLoader(Dataset):
    """Epic-Kitchens dataset loader"""

    def __init__(
            self,
            features_path,
            features_path_3D,
            start_idx,      # {video_id : array of start idx of a segmentation}
            gt_path,
            we,
            we_dim=300,
            max_words=10,
            train=True,
            clips_per_sample=2,
            clips_before=0,
            clips_filter_length=0,
    ):
        self.clips_per_sample = clips_per_sample
        self.clips_before = clips_before
        self.clips_filter_length = clips_filter_length
        self.verb_only = gt_path.split('/')[-1] == 'verb'
        self.data = self.__load_data(features_path, features_path_3D, start_idx, gt_path)
        self.we = we
        self.we_dim = we_dim
        self.max_words = max_words
        self.we_idx_to_word = dict()

        action_dict_file = os.path.join('/raid/xiaoyuz1/mstcn2', 'action_dictionary.pkl')
        self.actions_dict = None
        with open(action_dict_file, 'rb') as f:
            self.actions_dict = pickle.load(f)
        self.bkg_idx = np.max(list(self.actions_dict.values()))
        
        verb_path = '/home/xiaoyuz1/epic-kitchens-100-annotations/EPIC_100_verb_classes.csv'
        verb_class = pd.read_csv(verb_path, sep=',')
        self.parent_verb_idx_to_verb = verb_class.to_dict()['key']
        
    
    def create_annotation_tensor(self):
        all_verbs = list(self.actions_dict.keys())
        all_verbs = list(self.parent_verb_idx_to_verb.values())

        # all_verbs_l = []
        # for cap in all_verbs:
        #     all_verbs_l += self._tokenize_text(cap)
        # all_verbs_l = list(np.unique(all_verbs_l))

        # words = [word for word in all_verbs_l if word in self.we.vocab] #index_to_key
        # all_verbs_vec = self.we[words]
        # all_verbs_arr = np.zeros((len(all_verbs_vec), self.max_words, self.we_dim))
        # for i in range(len(all_verbs_vec)):
        #     all_verbs_arr[i,0,:] = all_verbs_vec[i]
        # self.all_verbs_l = all_verbs_l

        all_verbs_l = [self._tokenize_text(cap) for cap in all_verbs]
        all_verbs_l_cleaned = []
        all_verbs_arr = np.zeros((len(all_verbs_l), self.max_words, self.we_dim))
        for i in range(len(all_verbs_arr)):
            all_verbs_li = all_verbs_l[i]
            all_verbs_li = [word for word in all_verbs_li if word in self.we.vocab]
            all_verbs_l_cleaned.append(all_verbs_li)
            if len(all_verbs_li) == 0:
                continue
            all_verbs_vec = self.we[all_verbs_li]
            all_verbs_vec = all_verbs_vec[:self.max_words]
            all_verbs_arr[i,:len(all_verbs_vec),:] = all_verbs_vec
        self.all_verbs_l_cleaned = all_verbs_l_cleaned
        self.all_verbs_l = all_verbs_l
        return th.from_numpy(all_verbs_arr).float()

    def __load_data(self, features_path, features_path_3D, start_idx, gt_path):
        data = []
        for id in start_idx.keys():
          if os.path.isfile(os.path.join(features_path, id[0:3]+'/'+id+'.npy')):
            f_2D = np.load(os.path.join(features_path, id[0:3]+'/'+id+'.npy'))     # (x, 2048)
            f_3D = np.load(os.path.join(features_path_3D, id[0:3]+'/'+id+'.npy'))  # (x, 2048)
            
            '''
            gt = open(os.path.join(gt_path, id+'.txt'), 'r').read().split('\n')[:-1]
            start_indices = start_idx[id]
            non_bkg_mask = np.asarray(gt)[start_indices] != 'background'
            start_indices = list(start_indices)
            start_ends = np.asarray(list(zip(start_indices, start_indices[1:]+[len(f_3D)])))[non_bkg_mask] 

            num_samples = len(start_ends) // self.clips_per_sample + 1
            start_ends_group = np.pad(start_ends, [(0, num_samples*self.clips_per_sample - len(start_ends)), (0,0)], \
                mode='constant', constant_values=-1).reshape((num_samples, self.clips_per_sample, 2))
            
            for groups in start_ends_group:
                feat_2ds = []
                feat_3ds = []
                for start,end in groups:
                    if start < 0 or end < 0:
                        continue 
                    feat_2d = np.amax(f_2D[int(np.floor(start*16/12)):int(np.ceil(end*16/12))],axis=0).reshape((1,-1))
                    feat_2ds.append(feat_2d)
                    feat_3d = np.amax(f_3D[start:end],axis=0).reshape((1,-1))
                    feat_3ds.append(feat_3d)
                if len(feat_2ds) == 0 or len(feat_3ds) == 0:
                    continue
                
                starts_non_pad = groups[:,0][groups[:,0] > 0]
                data.append({'id': id, 'start': groups[0,0], 'end': groups[-1,-1], '2d': np.amax(feat_2ds, axis=0), \
                    '3d': np.amax(feat_3ds, axis=0), 'caption': ' '.join(list(np.asarray(gt)[starts_non_pad]))})
            '''
            if self.clips_before == 0:
                gt = open(os.path.join(gt_path, id+'.txt'), 'r').read().split('\n')[:-1]
                start_indices = start_idx[id]
                start_indices = list(start_indices)
                start_ends = np.asarray(list(zip(start_indices, start_indices[1:]+[len(f_3D)])))
                segment_length = start_ends[:,1] - start_ends[:,0]
                start_ends = start_ends[segment_length > self.clips_filter_length]
                if len(start_ends) < 1:
                    print(id)

                num_samples = len(start_ends) 
                for i in range(0,num_samples):
                    feat_2ds = []
                    feat_3ds = []
                    starts_non_pad = []
                    i_ends = min(i+self.clips_per_sample, num_samples)
                    for j in range(i, i_ends):
                        start,end = start_ends[j]
                        starts_non_pad.append(start)
                        feat_2d = np.amax(f_2D[int(np.floor(start*16/12)):int(np.ceil(end*16/12))],axis=0).reshape((1,-1))
                        feat_2ds.append(feat_2d)
                        feat_3d = np.amax(f_3D[start:end],axis=0).reshape((1,-1))
                        feat_3ds.append(feat_3d)
                    if len(feat_2ds) == 0 or len(feat_3ds) == 0:
                        continue
                    
                    data.append({'id': id, 'start': start_ends[i,0], 'end': start_ends[i_ends-1,-1], '2d': np.amax(feat_2ds, axis=0), \
                        '3d': np.amax(feat_3ds, axis=0), 'caption': ' '.join(list(np.asarray(gt)[starts_non_pad]))})
            else:   
                gt = open(os.path.join(gt_path, id+'.txt'), 'r').read().split('\n')[:-1]
                start_indices = start_idx[id]
                start_indices = list(start_indices)
                start_ends = np.asarray(list(zip(start_indices, start_indices[1:]+[len(f_3D)])))
                segment_length = start_ends[:,1] - start_ends[:,0]
                start_ends = start_ends[segment_length > self.clips_filter_length]
                if len(start_ends) < 1:
                    print(id)

                num_samples = len(start_ends) 
                for i in range(0,num_samples):
                    feat_2ds = []
                    feat_3ds = []
                    starts_non_pad = []
                    i_starts = max(i-self.clips_per_sample+1, 0)
                    for j in range(i_starts, i+1):
                        start,end = start_ends[j]
                        starts_non_pad.append(start)
                        feat_2d = np.amax(f_2D[int(np.floor(start*16/12)):int(np.ceil(end*16/12))],axis=0).reshape((1,-1))
                        feat_2ds.append(feat_2d)
                        feat_3d = np.amax(f_3D[start:end],axis=0).reshape((1,-1))
                        feat_3ds.append(feat_3d)
                    if len(feat_2ds) == 0 or len(feat_3ds) == 0:
                        continue
                    
                    data.append({'id': id, 'start': start_ends[i_starts,0], 'end': start_ends[i,-1], '2d': np.amax(feat_2ds, axis=0), \
                        '3d': np.amax(feat_3ds, axis=0), 'caption': ' '.join(list(np.asarray(gt)[starts_non_pad]))})
            
            # for i in range(len(start_idx[id])):
            #     start = start_idx[id][i]
            #     if i == len(start_idx[id]) - 1:
            #         end = len(f_3D)
            #     else:
            #         end = start_idx[id][i+1]
                
            #     data.append({'id': id, 'start': start, 'end': end, '2d': np.amax(f_2D[int(np.floor(start*16/12)):int(np.ceil(end*16/12))],axis=0).reshape((1,-1)), '3d': np.amax(f_3D[start:end],axis=0).reshape((1,-1)), 'caption': gt[start]})
        return data

    def _zero_pad_tensor(self, tensor, size):
        if len(tensor) >= size:
            return tensor[:size]
        else:
            zero = np.zeros((size - len(tensor), self.we_dim), dtype=np.float32)
            return np.concatenate((tensor, zero), axis=0)

    def _words_to_we(self, words):
        words = [word for word in words if word in self.we.vocab] #index_to_key
        if words:
            we = self._zero_pad_tensor(self.we[words], self.max_words)
            return th.from_numpy(we)
        else:
            return th.zeros(self.max_words, self.we_dim) 

    def _tokenize_text(self, sentence):
        w = re.findall(r"[\w']+", str(sentence))
        return w    
    
    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        feat_2d = F.normalize(th.from_numpy(self.data[idx]['2d']).float(), dim=0)
        feat_3d = F.normalize(th.from_numpy(self.data[idx]['3d']).float(), dim=0)
        video = th.cat((feat_2d, feat_3d), 1)[0]
        cap = self.data[idx]['caption']
        if self.verb_only:
            cap_class = self.actions_dict.get(cap, self.bkg_idx)
        else:
            cap_class = -1
        cap_words = self._tokenize_text(cap)
        caption = self._words_to_we(cap_words)
        
        cap_words_filtered = [word for word in cap_words if word in self.we.vocab]
        caption_indices = [self.we.vocab[word].index for word in cap_words_filtered]
        caption_indices_tensor = np.array(caption_indices).reshape(-1,)
        if len(caption_indices_tensor) > self.max_words:
            caption_indices_tensor = caption_indices_tensor[:self.max_words]
        else:
            zero = np.zeros(self.max_words - len(caption_indices_tensor), dtype=np.float32)
            caption_indices_tensor = np.concatenate((caption_indices_tensor, zero), axis=0)
        caption_indices_tensor = th.FloatTensor(caption_indices_tensor)
        
        return {'video': video, 'text': caption, 'caption_cls': cap_class, 'caption_idx': caption_indices_tensor, 'video_id': self.data[idx]['id'], 'start': self.data[idx]['start'], 'end': self.data[idx]['end']}
