import numpy as np

import torch
import torch.nn as nn
from torch.utils.data import Dataset

import torchvision.models
from torchvision import transforms

from augmentation.SpecTransforms import ResizeSpectrogram
from augmentation.RandomErasing import RandomErasing

random_erasing = RandomErasing()

class Task5Model(nn.Module):

    def __init__(self, num_classes):
        
        super().__init__()
        self.bw2col = nn.Sequential(
            nn.BatchNorm2d(1),
            nn.Conv2d(1, 10, 1, padding=0), nn.ReLU(),
            nn.Conv2d(10, 3, 1, padding=0), nn.ReLU())

        self.mv2 = torchvision.models.mobilenet_v2(pretrained=True)

        self.final = nn.Sequential(
            nn.Linear(1280, 512), nn.ReLU(), nn.BatchNorm1d(512),
            nn.Linear(512, num_classes))

    def forward(self, x):
        x = self.bw2col(x)
        x = self.mv2.features(x)
        x = x.max(dim=-1)[0].max(dim=-1)[0]
        x = self.final(x)
        return x

class AudioDataset(Dataset):

    def __init__(self, df, feature_type="logmelspec", spec_transform=None, image_transform=None, resize=None, data_type='train', input_folder=None):

        self.df = df
        self.feature_type = feature_type
        self.filenames = list(set(df.index.tolist()))
        self.data_type = data_type
        self.input_folder = input_folder

        self.spec_transform = spec_transform
        self.image_transform = image_transform
        self.resize = ResizeSpectrogram(frames=resize)
        self.pil = transforms.ToPILImage()

        self.channel_means = np.load('./data/statistics/channel_means_{}.npy'.format(feature_type))
        self.channel_stds = np.load('./data/statistics/channel_stds_{}.npy'.format(feature_type))

        self.channel_means = self.channel_means.reshape(1,-1,1)
        self.channel_stds = self.channel_stds.reshape(1,-1,1)

    def __len__(self):
        return len(self.filenames)

    def __getitem__(self, idx):

        file_name = self.filenames[idx]

        if self.data_type!="predict":
            labels = self.df.loc[file_name].to_numpy()

        if self.data_type=='predict':
            sample = np.load('./data/' + self.feature_type + f'/{self.input_folder}/' + file_name + '.npy')
        else:
            sample = np.load('./data/' + self.feature_type + f'/{self.data_type}/' + file_name + '.npy')

        if self.resize:
            sample = self.resize(sample)
            # this is going to resize to our desired spectrogram size! Hence even a 2/3s audio segment
            # which will have spectrogram size (128, 191) will be padded with zeros to obtain spectrogram
            # corresponding to 10s audio file - (128, 191 ) + zero_columns -> (128, 636)
            # the zero regions in the spectrogram should be interpreted as silent regions

        sample = (sample-self.channel_means)/self.channel_stds
        sample = torch.Tensor(sample)

        if self.spec_transform and self.data_type!='predict':
            sample = self.spec_transform(sample)

#         sample = sample.transpose(0,1)
        
        if self.image_transform and self.data_type!='predict':
            # min-max transformation
            this_min = sample.min()
            this_max = sample.max()
            sample = (sample - this_min) / (this_max - this_min)
            
            # randomly cycle the file
            i = np.random.randint(sample.shape[1])
            sample = torch.cat([
                sample[:, i:, :],
                sample[:, :i, :]],
                dim=1)
            # apply albumentations transforms
            sample = np.array(self.pil(sample))
            sample = self.image_transform(image=sample)
            sample = sample['image']
            sample = sample[None, :, :].permute(0, 2, 1)
            
            # apply random erasing
            sample = random_erasing(sample.clone().detach())
            
            # revert min-max transformation
            sample = (sample * (this_max - this_min)) + this_min
            
        if len(sample.shape)<3:
            sample = torch.unsqueeze(sample, 0)

        if  self.data_type!='predict':
            labels = torch.FloatTensor(labels)

        data = {}
        data['data'], data['file_name'] = sample, file_name

        if self.data_type!='predict':
            data['labels'] = labels
            
        return data

def mixup_data(x, y, alpha):

    '''Compute the mixup data. Return mixed inputs, pairs of targets, and lambda'''
    if alpha > 0.:
        lam = np.random.beta(alpha, alpha)
    else:
        lam = 1.
    batch_size = x.size()[0]
    index = torch.randperm(batch_size).cuda()
    mixed_x = lam * x + (1 - lam) * x[index,:]
    y_a, y_b = y, y[index]
    return mixed_x, y_a, y_b, lam
