from __future__ import absolute_import, division, print_function
import os
os.environ["CUDA_VISIBLE_DEVICES"] = '0'
import argparse
import tqdm

import torch
from torch.utils.data import DataLoader

from networks import UniFuse, Equi
import datasets
from metrics import Evaluator
from saver import Saver
#from networks.deeplab_xception import  DeepLabv3_plus
#from networks.vae_deeplab_xception import  DeepLabv3_plus
from networks.MAGCA_deeplab_xception import DeepLabv3_plus
#from networks.VAE_MAGCA_deeplab_xception import DeepLabv3_plus


parser = argparse.ArgumentParser(description="360 Degree Panorama Depth Estimation Test")

parser.add_argument("--data_path", default="/home/wolian/disk1/Stanford2D3D/", type=str, help="path to the dataset.")
parser.add_argument("--dataset", default="matterport3d", choices=["3d60", "panosuncg", "stanford2d3d", "matterport3d"],
                    type=str, help="dataset to evaluate on.")

parser.add_argument("--load_weights_dir", type=str, help="folder of model to load")

parser.add_argument("--num_workers", type=int, default=4, help="number of dataloader workers")
parser.add_argument("--batch_size", type=int, default=8, help="batch size")

parser.add_argument("--median_align", action="store_true", help="if set, apply median alignment in evaluation")
parser.add_argument("--save_samples", action="store_true", help="if set, save the depth maps and point clouds")

parser.add_argument("--ehc", type=str, help="folder of model to load")
parser.add_argument("--vae", type=str, help="folder of model to load")
parser.add_argument("--distribution", type=str, default='normal')

settings = parser.parse_args()
settings.data_path = '/test/depth/data'
settings.dataset = '3d60' #stanford2d3d
settings.ehc = False
settings.vae = False
settings.distribution = 'normal'
settings.save_samples = True
#settings.load_weights_dir = '/test/depth/code/UniFuse-Unidirectional-Fusion-main-v3/UniFuse-Unidirectional-Fusion-main/UniFuse/Logs/stanford2d3d_deeplab_withpretrained_MAGCA/weights_90'
#settings.load_weights_dir = '/test/depth/code/UniFuse-Unidirectional-Fusion-main-v3/UniFuse-Unidirectional-Fusion-main/UniFuse/Logs/3d60_deeplab_withpretrained/weights_30'
#settings.load_weights_dir = '/test/depth/code/UniFuse-Unidirectional-Fusion-main-v3/UniFuse-Unidirectional-Fusion-main/UniFuse/Logs/3d60_deeplab_MAGCA_VAE_Normal_FT/panodepth/models/weights_5'
settings.load_weights_dir = 'model90'
#settings.load_weights_dir = 'Logs/3d60_deeplab_sitanfu/panodepth/models/weights_0'
# settings.load_weights_dir = 'Logs/stanford2d3d_deeplab_withpretrained_MAGCA/weights_90'
def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    load_weights_folder = os.path.expanduser(settings.load_weights_dir)
    model_path = os.path.join(load_weights_folder, "model.pth")
    model_dict = torch.load(model_path)

    # data
    datasets_dict = {"3d60": datasets.ThreeD60,
                     "panosuncg": datasets.PanoSunCG,
                     "stanford2d3d": datasets.Stanford2D3D,
                     "matterport3d": datasets.Matterport3D}
    dataset = datasets_dict[settings.dataset]

    fpath = os.path.join(os.path.dirname(__file__), "datasets", "{}_{}.txt")

    test_file_list = fpath.format(settings.dataset, "test")

    test_dataset = dataset(settings.data_path, test_file_list,
                           model_dict['height'], model_dict['width'], is_training=False)
    test_loader = DataLoader(test_dataset, settings.batch_size, False,
                             num_workers=settings.num_workers, pin_memory=True, drop_last=False)
    num_test_samples = len(test_dataset)
    num_steps = num_test_samples // settings.batch_size
    print("Num. of test samples:", num_test_samples, "Num. of steps:", num_steps, "\n")

    model = DeepLabv3_plus(ehc=settings.ehc, vae=settings.vae)
    model.to(device)
    #model_state_dict = model.state_dict()
    #model.load_state_dict({k: v for k, v in model_dict.items() if k in model_state_dict})
    model.load_state_dict(torch.load(os.path.join(settings.load_weights_dir, 'model.pth')), False)
    model.eval()

    evaluator = Evaluator(settings.median_align)
    evaluator.reset_eval_metrics()
    saver = Saver(load_weights_folder)
    pbar = tqdm.tqdm(test_loader)
    pbar.set_description("Testing")

    with torch.no_grad():
        for batch_idx, inputs in enumerate(pbar):

            outputs = model.infer(inputs)

            pred_depth = outputs["pred"].detach().cpu()

            gt_depth = inputs["gt_depth"]
            mask = inputs["val_mask"]
            for i in range(gt_depth.shape[0]):
                evaluator.compute_eval_metrics(gt_depth[i:i + 1], pred_depth[i:i + 1], mask[i:i + 1])

            if settings.save_samples:
                saver.save_samples(inputs["rgb"], gt_depth, pred_depth, mask)

    evaluator.print(load_weights_folder)


if __name__ == "__main__":
    main()
