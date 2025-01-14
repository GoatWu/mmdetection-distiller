import torch.nn as nn
import torch.nn.functional as F
import torch

from .utils import weight_reduce_loss
from ..builder import DISTILL_LOSSES


@DISTILL_LOSSES.register_module()
class ChannelWiseDivergence(nn.Module):

    """PyTorch version of `Channel-wise Distillation for Semantic Segmentation
     <https://arxiv.org/abs/2011.13256>`_.
   
    Args:
        student_channels(int): Number of channels in the student's feature map.
        teacher_channels(int): Number of channels in the teacher's feature map.
        name(str): 
        tau (float, optional): Temperature coefficient. Defaults to 1.0.
        weight (float, optional): Weight of loss.Defaults to 1.0.
        
    """
    def __init__(self,
                 student_channels,
                 teacher_channels,
                 name,
                 tau=1.0,
                 weight=1.0,
                 ):
        super(ChannelWiseDivergence, self).__init__()
        self.tau = tau
        self.loss_weight = weight
        
        self.m1 = nn.AvgPool2d((2, 2), stride=(2, 2), padding=(0, 0))
        self.m2 = nn.AvgPool2d((2, 2), stride=(2, 2), padding=(0, 1))
        self.m3 = nn.AvgPool2d((2, 2), stride=(2, 2), padding=(1, 0))
        self.m4 = nn.AvgPool2d((2, 2), stride=(2, 2), padding=(1, 1))
    
        if student_channels != teacher_channels:
            self.align = nn.Conv2d(student_channels, teacher_channels, kernel_size=1, stride=1, padding=0)
        else:
            self.align = None


    def forward(self,
                preds_S,
                preds_T):
        """Forward function."""
#         assert preds_S.shape[-2:] == preds_T.shape[-2:],'the output dim of teacher and student differ: {}, {}'.format(preds_S.shape, preds_T.shape)
        N,C,W,H = preds_S.shape
    
        if W % 2 == 0 and H % 2 == 0:
            preds_S = self.m1(preds_S)
        elif W % 2 == 0 and H % 2 == 1:
            preds_S = self.m2(preds_S)
        elif W % 2 == 1 and H % 2 == 0:
            preds_S = self.m3(preds_S)
        else:
            preds_S = self.m4(preds_S)
        assert preds_S.shape[-2:] == preds_T.shape[-2:],'the output dim of teacher and student differ: {}, {}'.format(preds_S.shape, preds_T.shape)
        
        N,C,W,H = preds_S.shape

        if self.align is not None:
            preds_S = self.align(preds_S)

        softmax_pred_T = F.softmax(preds_T.view(-1,W*H)/self.tau, dim=1)
        softmax_pred_S = F.softmax(preds_S.view(-1,W*H)/self.tau, dim=1)
        
        logsoftmax = torch.nn.LogSoftmax(dim=1)
        loss = torch.sum( - softmax_pred_T * logsoftmax(preds_S.view(-1,W*H)/self.tau)) * (self.tau ** 2)
        return self.loss_weight * loss / (C * N)