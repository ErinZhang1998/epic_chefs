#!/usr/bin/python2.7

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import optim
import copy
import numpy as np
import wandb
from eval import single_eval_scores
from visualize import visualize, plot_table
from layers import SingleStageModel, GCNStageModel, exchange_time
import os 

loss_weight = [2.42, 2.58, 2.0025, 3.4317, 3.9258, 3.4896, 4.3452, 2.7867, 4.7968, 3.632, 2.8122, 4.3794, 4.0578, 5.1289, 4.5099, 5.3965, 5.1013, 5.4486, 5.3951, 4.3941, 5.5349, 5.4607, 5.4503, 5.195, 5.6235, 5.4568, 5.7294, 5.2859, 6.2777, 5.4185, 5.5121, 6.964, 6.7155, 6.662, 6.1543, 6.5912, 6.3752, 6.1227, 6.2823, 6.4502, 6.3478, 6.9088, 6.0572, 6.8712, 6.9043, 5.9277, 6.4784, 6.0136, 6.1658, 6.018, 7.3134, 5.8112, 5.8797, 6.915, 7.7222, 6.8789, 7.8932, 6.2395, 6.9277, 7.0426, 7.0201, 7.515, 8.2545, 7.3117, 7.6911, 7.9406, 7.9759, 7.7007, 7.4564, 7.1744, 8.068, 8.9555, 6.1383, 8.4579, 7.0757, 8.6479, 8.2438, 6.3452, 7.6783, 8.5644, 8.9496, 8.6475, 7.4734, 9.873, 8.0403, 8.618, 9.1365, 8.5578, 8.1769, 8.989, 9.757, 10.2004, 8.3307, 12.1194, 9.5974, 12.5848, 9.6096, 1.3277]
# [11.0, 13.0, 7.0, 30.0, 50.0, 32.0, 77.0, 16.0, 100.0, 37.0, 16.0, 79.0, 57.0, 100.0, 90.0, 100.0, 100.0, 100.0, 100.0, 81.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 3.0]

class MultiStageModel(nn.Module):
    def __init__(self, num_stages, num_layers, num_f_maps, df_size, dim, num_classes):
        super(MultiStageModel, self).__init__()
        self.stage1 = SingleStageModel(num_layers, num_f_maps, dim, num_classes)
        self.stages = nn.ModuleList([copy.deepcopy(GCNStageModel(num_layers, num_f_maps, df_size, num_classes, num_classes)) 
            for s in range(num_stages-1)])

    def forward(self, x, mask):
        exchange_outputs = []
        exchange_labels = []
        exchange_cls_outputs = []

        ex_x, ex_label = exchange_time(x)
        out, ex_out, ex_gt, ex_pred = self.stage1(x, mask, ex_x, ex_label)
        outputs = out.unsqueeze(0)
        exchange_outputs.append(ex_out)
        exchange_labels.append(ex_gt)
        exchange_cls_outputs.append(ex_pred)
        for s in self.stages:
            out, ex_out, ex_gt, ex_pred = s(F.softmax(out, dim=1) * mask[:, 0:1, :], mask, F.softmax(ex_pred, dim=1) * mask[:, 0:1, :], ex_label)
            outputs = torch.cat((outputs, out.unsqueeze(0)), dim=0)
            exchange_outputs.append(ex_out)
            exchange_labels.append(ex_gt)
            exchange_cls_outputs.append(ex_pred)
        exchange_outputs = torch.stack(exchange_outputs)
        exchange_labels = torch.stack(exchange_labels)
        exchange_cls_outputs = torch.stack(exchange_cls_outputs)

        return outputs, exchange_outputs, exchange_labels, exchange_cls_outputs

# class MultiStageModel(nn.Module):
#     def __init__(self, num_stages, num_layers, num_f_maps, dim, num_classes):
#         super(MultiStageModel, self).__init__()
#         self.stage1 = SingleStageModel(num_layers, num_f_maps, dim, num_classes)
#         self.stages = nn.ModuleList([copy.deepcopy(SingleStageModel(num_layers, num_f_maps, num_classes, num_classes)) for s in range(num_stages-1)])

#     def forward(self, x, mask):
#         out = self.stage1(x, mask)
#         outputs = out.unsqueeze(0)
#         for s in self.stages:
#             out = s(F.softmax(out, dim=1) * mask[:, 0:1, :], mask)
#             outputs = torch.cat((outputs, out.unsqueeze(0)), dim=0)
#         return outputs

# class SingleStageModel(nn.Module):
#     def __init__(self, num_layers, num_f_maps, dim, num_classes):
#         super(SingleStageModel, self).__init__()
#         self.conv_1x1 = nn.Conv1d(dim, num_f_maps, 1)
#         self.layers = nn.ModuleList([copy.deepcopy(DilatedResidualLayer(2 ** i, num_f_maps, num_f_maps)) for i in range(num_layers)])
#         self.conv_out = nn.Conv1d(num_f_maps, num_classes, 1)

#     def forward(self, x, mask):
#         out = self.conv_1x1(x)
#         for layer in self.layers:
#             out = layer(out, mask)
#         out = self.conv_out(out) * mask[:, 0:1, :]
#         return out


# class DilatedResidualLayer(nn.Module):
#     def __init__(self, dilation, in_channels, out_channels):
#         super(DilatedResidualLayer, self).__init__()
#         self.conv_dilated = nn.Conv1d(in_channels, out_channels, 3, padding=dilation, dilation=dilation)
#         self.conv_1x1 = nn.Conv1d(out_channels, out_channels, 1)
#         self.dropout = nn.Dropout()

#     def forward(self, x, mask):
#         out = F.relu(self.conv_dilated(x))
#         out = self.conv_1x1(out)
#         out = self.dropout(out)
#         return (x + out) * mask[:, 0:1, :]

class Trainer:
    def __init__(self, wandb_run_name, num_blocks, num_layers, num_f_maps, dim, num_classes, background_class_idx, df_size, val_every=50, visualize_every=5, filter_background = False):
        self.model = MultiStageModel(num_blocks, num_layers, num_f_maps, df_size, dim, num_classes)
        self.loss_weight = torch.Tensor(loss_weight).to('cuda')
        self.ce = nn.CrossEntropyLoss(weight=self.loss_weight)#ignore_index=-100)
        self.ce2 = nn.CrossEntropyLoss(ignore_index=-100)
        self.mse = nn.MSELoss(reduction='none')
        self.num_classes = num_classes
        self.background_class_idx = background_class_idx

        self.val_every = val_every
        self.visualize_every = visualize_every
        self.wandb_run_name = wandb_run_name
        print("===> Trainer with wandb run named as: ", self.wandb_run_name)

        self.videos_to_visualize = ['P16_04', \
            'P23_05', \
            'P29_05', \
            'P01_15',
            'P05_07',
            'P32_04',
            'P26_39',
            'P19_05',
            'P01_11',
            'P04_26',
            'P04_32',
            'P14_06',
            'P19_05',
            'P28_15',
            'P07_17']

        self.filter_background = filter_background

        self.cur_subplots = 0

    def train(self, save_dir, batch_gen, val_batch_gen, num_epochs, batch_size, learning_rate, device, \
        scheduler_step, scheduler_gamma):
        self.model.train()
        batch_gen.reset()
        
        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=scheduler_step, gamma=scheduler_gamma)

        cnt = 0
        for epoch in range(num_epochs):
            epoch_loss = 0
            correct = 0
            correct_nobkg = 0
            total = 0
            batch_count = 0
            f1_score = 0
            edit_dist = 0
            f1_edit_count = 0
            batch_gen.reset()

            while batch_gen.has_next():
                self.model.to(device)
                batch_count += 1

                batch_input, batch_target, mask, _ = batch_gen.next_batch(batch_size)
                batch_input, batch_target, mask = batch_input.to(device), batch_target.to(device), mask.to(device)
                optimizer.zero_grad()
                # predictions = self.model(batch_input, mask)
                predictions, exchange_outputs, exchange_labels, exchange_cls_outputs = self.model(batch_input, mask)
                # print(predictions.shape, batch_target.shape)
                loss = 0
                for p in predictions:
                    loss += self.ce(p.transpose(2, 1).contiguous().view(-1, self.num_classes), batch_target.view(-1))
                    loss += 0.15*torch.mean(torch.clamp(self.mse(F.log_softmax(p[:, :, 1:], dim=1), F.log_softmax(p.detach()[:, :, :-1], dim=1)), min=0, max=16)*mask[:, :, 1:])
                
                for p in exchange_cls_outputs:
                    loss += 0.5*self.ce(p.transpose(2, 1).contiguous().view(-1, self.num_classes), batch_target.view(-1))
                    loss += 0.15*torch.mean(torch.clamp(self.mse(F.log_softmax(p[:, :, 1:], dim=1), F.log_softmax(p.detach()[:, :, :-1], dim=1)), min=0, max=16)*mask[:, :, 1:])

                for pred, gt in zip(exchange_outputs, exchange_labels):
                    loss += 2*self.ce2(pred.transpose(2, 1).contiguous().view(-1, 2), gt.view(-1))

                epoch_loss += loss.item()
                loss.backward()
                optimizer.step()

                # if self.filter_background:
                #     mask_bkg = batch_target != self.background_class_idx
                # else:
                #     mask_bkg = batch_target >= 0
                mask_bkg = batch_target != self.background_class_idx
                _, predicted = torch.max(predictions[-1].data, 1)
                correct += ((predicted == batch_target).float()*mask[:, 0, :].squeeze(1)).sum().item()
                correct_nobkg += ((predicted == batch_target).float()*mask[:, 0, :]*mask_bkg.squeeze(1)).sum().item()
                
                total += torch.sum(mask[:, 0, :]).item()
                if epoch >= num_epochs * 0.8:
                    results_dict = single_eval_scores(batch_target, predicted, bg_class = [self.num_classes-1])
                    f1_score += results_dict['F1@ 0.50']
                    edit_dist += results_dict['edit']

                if cnt % self.val_every == 0:
                    self.evaluate(val_batch_gen, num_epochs, epoch, cnt, device, batch_size)

                    wandb_dict = {'train/epoch_loss' : epoch_loss / batch_count, \
                        'train/acc' : float(correct)/total,
                        'train/acc_nobkg' : float(correct_nobkg)/total,
                        }
                    if epoch >= num_epochs * 0.8:
                        wandb_dict['train/edit'] = float(edit_dist) / batch_count
                        wandb_dict['train/F1'] = float(f1_score) / batch_count

                    wandb.log(wandb_dict, step=cnt)

                cnt += 1
                

            scheduler.step()
            save_path = os.path.join(save_dir, '{}'.format(self.wandb_run_name))
            if not os.path.exists(save_path):
                os.mkdir(save_path)
            model_path = os.path.join(save_path, 'epoch-{}.model'.format(epoch+1))
            optimizer_path = os.path.join(save_path, 'epoch-{}.opt'.format(epoch+1))
            
            
            torch.save(self.model.state_dict(), model_path)
            torch.save(optimizer.state_dict(), optimizer_path)

            wandb.save(model_path)
            wandb.save(optimizer_path)
            
            print("Training: [epoch %d]: epoch loss = %f,   acc = %f" % (epoch + 1, epoch_loss / len(batch_gen.list_of_examples), float(correct)/total))

    def evaluate(self, val_batch_gen, num_epochs, epoch, cnt, device, batch_size):
        self.model.eval()

        with torch.no_grad():
            correct = 0
            correct_nobkg = 0
            total = 0
            epoch_loss = 0
            f1_score = 0
            edit_dist = 0
            val_batch_gen.reset()

            while val_batch_gen.has_next():
                self.model.to(device)
                batch_input, batch_target, mask, batch_video_ids = val_batch_gen.next_batch(batch_size)
                batch_input, batch_target, mask = batch_input.to(device), batch_target.to(device), mask.to(device)

                predictions, _, _, _ = self.model(batch_input, mask)
                
                loss = 0
                for p in predictions:
                    loss += self.ce(p.transpose(2, 1).contiguous().view(-1, self.num_classes), batch_target.view(-1))
                    loss += 0.15*torch.mean(torch.clamp(self.mse(F.log_softmax(p[:, :, 1:], dim=1), F.log_softmax(p.detach()[:, :, :-1], dim=1)), min=0, max=16)*mask[:, :, 1:])

                epoch_loss += loss.item()
                mask_bkg = batch_target != self.background_class_idx
                _, predicted = torch.max(predictions[-1].data, 1)
                correct += ((predicted == batch_target).float()*mask[:, 0, :].squeeze(1)).sum().item()
                correct_nobkg += ((predicted == batch_target).float()*mask[:, 0, :]*mask_bkg.squeeze(1)).sum().item()
                total += torch.sum(mask[:, 0, :]).item()

                torch.cuda.empty_cache()
                if epoch >= num_epochs * 0.8:
                    results_dict = single_eval_scores(batch_target, predicted, bg_class = [self.num_classes-1])
                    f1_score += results_dict['F1@ 0.50']
                    edit_dist += results_dict['edit']


                batch_video_id = batch_video_ids[0]
                if batch_video_id in self.videos_to_visualize: 
                    if (epoch+1) % self.visualize_every == 0:
                        
                        self.cur_subplots += 1
                        val_batch_gen.reset_fig(1)
                        
                        ax_name = val_batch_gen.ax.flat[0]
                        fig_name =  val_batch_gen.fig
                        color_name = val_batch_gen.colors
                        cap = 'Pred_Epoch_{}'.format(epoch)
                        visualize(cnt, batch_video_id, predicted, ax_name, fig_name, color_name, cap)
                    
                        #if epoch == num_epochs - 1:
                        ax_name = val_batch_gen.ax.flat[1]
                        fig_name =  val_batch_gen.fig
                        color_name = val_batch_gen.colors
                        cap = 'GT'
                        visualize(cnt, batch_video_id, batch_target, ax_name, fig_name, color_name, cap)
                    
                    plot_table(cnt, batch_video_id, predicted, batch_target, val_batch_gen.actions_dict_rev)

            wandb_dict = {'validate/epoch_loss' : epoch_loss / len(val_batch_gen.list_of_examples), \
                'validate/acc' : float(correct)/total,
                'validate/acc_nobkg' : float(correct_nobkg)/total,
                }
            if epoch >= num_epochs * 0.8:
                wandb_dict['validate/edit'] = float(edit_dist) / len(val_batch_gen.list_of_examples)
                wandb_dict['validate/F1'] = float(f1_score) / len(val_batch_gen.list_of_examples)

            wandb.log(wandb_dict, step=cnt)
            print("Validate: [epoch %d]: epoch loss = %f,   acc = %f" % (epoch + 1, epoch_loss / len(val_batch_gen.list_of_examples), float(correct)/total))
    
    def predict(self, model_dir, results_dir, features_path, vid_list_file, epoch, actions_dict, device, sample_rate):
        self.model.eval()
        with torch.no_grad():
            self.model.to(device)
            self.model.load_state_dict(torch.load(model_dir + "/epoch-" + str(epoch) + ".model"))
            file_ptr = open(vid_list_file, 'r')
            list_of_vids = file_ptr.read().split('\n')[:-1]
            file_ptr.close()
            for vid in list_of_vids:
                print(vid)
                features = np.load(features_path + vid.split('.')[0] + '.npy')
                features = features[:, ::sample_rate]
                input_x = torch.tensor(features, dtype=torch.float)
                input_x.unsqueeze_(0)
                input_x = input_x.to(device)
                predictions = self.model(input_x, torch.ones(input_x.size(), device=device))
                _, predicted = torch.max(predictions[-1].data, 1)
                predicted = predicted.squeeze()
                recognition = []
                for i in range(len(predicted)):
                    recognition = np.concatenate((recognition, [actions_dict.keys()[actions_dict.values().index(predicted[i].item())]]*sample_rate))
                f_name = vid.split('/')[-1].split('.')[0]
                f_ptr = open(results_dir + "/" + f_name, "w")
                f_ptr.write("### Frame level recognition: ###\n")
                f_ptr.write(' '.join(recognition))
                f_ptr.close()
