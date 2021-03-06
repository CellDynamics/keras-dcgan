"""Deep Convolutional Generative Adversarial Networks."""
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import Reshape
from keras.layers.core import Activation
from keras.layers.normalization import BatchNormalization
from keras.layers.convolutional import UpSampling2D
from keras.layers.convolutional import MaxPooling2D, Conv2D
from keras.layers.core import Flatten
from keras.optimizers import SGD
from keras.datasets import mnist
import numpy as np
import scipy.misc as misc
from PIL import Image
import argparse
import math
import os
from os import path as p
import glob

output_folder = "./out"


def generator_model():
    model = Sequential()
    model.add(Dense(input_dim=100, units=1024))
    model.add(Activation('tanh'))
    model.add(Dense(128 * 7 * 7))
    model.add(BatchNormalization())
    model.add(Activation('tanh'))
    model.add(Reshape((7, 7, 128), input_shape=(128 * 7 * 7,)))
    model.add(UpSampling2D(size=(4, 4)))
    model.add(Conv2D(64, (5, 5), padding='same'))
    model.add(Activation('tanh'))
    model.add(UpSampling2D(size=(4, 4)))
    model.add(Conv2D(1, (5, 5), padding='same'))
    model.add(Activation('tanh'))
    return model


def discriminator_model():
    model = Sequential()
    model.add(Conv2D(
        64, (5, 5),
        padding='same',
        input_shape=(112, 112, 1)))  # 28,28 for mnist
    model.add(Activation('tanh'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Conv2D(128, (5, 5)))
    model.add(Activation('tanh'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Flatten())
    model.add(Dense(1024))
    model.add(Activation('tanh'))
    model.add(Dense(1))
    model.add(Activation('sigmoid'))
    return model


def generator_containing_discriminator(generator, discriminator):
    model = Sequential()
    model.add(generator)
    discriminator.trainable = False
    model.add(discriminator)
    return model


def combine_images(generated_images):
    num = generated_images.shape[0]
    width = int(math.sqrt(num))
    height = int(math.ceil(float(num) / width))
    shape = generated_images.shape[2:]
    image = np.zeros((height * shape[0], width * shape[1]), dtype=generated_images.dtype)
    for index, img in enumerate(generated_images):
        i = int(index / width)
        j = index % width
        image[i * shape[0]:(i + 1) * shape[0], j * shape[1]:(j + 1) * shape[1]] = img[0, :, :]
    return image


def load_dataset(location=None, pattern=None):
    """Load datasets.

    Args:
        location - path to images or None for minst data
        pattern - regexp file name pattern or None

    Returns:
        Array [N,x,y] of N images of x,y size each

    """
    if not location:
        (X_train, _), (_, _) = mnist.load_data()
        print("Use MNIST")
        return X_train

    files = glob.glob(p.join(location, pattern))
    if not files:
        raise ValueError("No files found in " + location)
    # load and store images
    # lad first and check reolution - assume same for all
    test = misc.imread(files[0])
    # output array
    images = np.zeros((len(files),) + test.shape)
    for count, f in enumerate(files):
        test = misc.imread(f)
        images[count, :, :] = test
    print("Loaded %d images of size" % len(images), test.shape)
    return images


def train(BATCH_SIZE):
    epochs = 1000  # TODO Add to command line params
    X_train = load_dataset(location="/home/baniuk/Documents/Kay-copy/FLU+DIC/out", pattern="mask*.png")
    X_train = (X_train.astype(np.float32) - 127.5) / 127.5
    X_train = X_train.reshape((X_train.shape[0], 1) + X_train.shape[1:])
    discriminator = discriminator_model()
    generator = generator_model()
    discriminator_on_generator = generator_containing_discriminator(generator, discriminator)
    d_optim = SGD(lr=0.0005, momentum=0.9, nesterov=True)
    g_optim = SGD(lr=0.0005, momentum=0.9, nesterov=True)
    generator.compile(loss='binary_crossentropy', optimizer="SGD")
    discriminator_on_generator.compile(loss='binary_crossentropy', optimizer=g_optim)
    discriminator.trainable = True
    discriminator.compile(loss='binary_crossentropy', optimizer=d_optim)
    noise = np.zeros((BATCH_SIZE, 100))
    for epoch in range(epochs):
        print("Epoch is", epoch, "-", "Number of batches", int(X_train.shape[0] / BATCH_SIZE))
        for index in range(int(X_train.shape[0] / BATCH_SIZE)):
            for i in range(BATCH_SIZE):
                noise[i, :] = np.random.uniform(-1, 1, 100)
            image_batch = X_train[index * BATCH_SIZE:(index + 1) * BATCH_SIZE]
            image_batch = image_batch.transpose((0, 2, 3, 1))
            generated_images = generator.predict(noise, verbose=0)
            if index % 20 == 0:
                generated_images_tosave = generated_images.transpose((0, 3, 1, 2))
                image = combine_images(generated_images_tosave)
                image = image * 127.5 + 127.5
                Image.fromarray(image.astype(np.uint8)).save(p.join(output_folder, (str(epoch) + "_"
                                                                                    + str(index) + ".png")))
            # print(image_batch.shape, generated_images.shape)  # (128, 28, 28, 1) (128, 28, 28, 1) MNIST
            X = np.concatenate((image_batch, generated_images))
            y = [1] * BATCH_SIZE + [0] * BATCH_SIZE
            d_loss = discriminator.train_on_batch(X, y)
            # print("batch %d d_loss : %f" % (index, d_loss))
            for i in range(BATCH_SIZE):
                noise[i, :] = np.random.uniform(-1, 1, 100)
            discriminator.trainable = False
            g_loss = discriminator_on_generator.train_on_batch(noise, [1] * BATCH_SIZE)
            discriminator.trainable = True
            print("batch %d g_loss : %f" % (index, g_loss), " ", "batch %d d_loss : %f" % (index, d_loss))
            if index % 10 == 9:
                generator.save_weights(p.join(output_folder, 'generator'), True)
                discriminator.save_weights(p.join(output_folder, 'discriminator'), True)


def generate(BATCH_SIZE, nice=False):
    generator = generator_model()
    generator.compile(loss='binary_crossentropy', optimizer="SGD")
    generator.load_weights(p.join(output_folder, 'generator'))
    if nice:
        discriminator = discriminator_model()
        discriminator.compile(loss='binary_crossentropy', optimizer="SGD")
        discriminator.load_weights('discriminator')
        noise = np.zeros((BATCH_SIZE * 20, 100))
        for i in range(BATCH_SIZE * 20):
            noise[i, :] = np.random.uniform(-1, 1, 100)
        generated_images = generator.predict(noise, verbose=1)
        d_pret = discriminator.predict(generated_images, verbose=1)
        index = np.arange(0, BATCH_SIZE * 20)
        index.resize((BATCH_SIZE * 20, 1))
        pre_with_index = list(np.append(d_pret, index, axis=1))
        pre_with_index.sort(key=lambda x: x[0], reverse=True)
        nice_images = np.zeros((BATCH_SIZE, 1) +
                               (generated_images.shape[2:]), dtype=np.float32)
        for i in range(int(BATCH_SIZE)):
            idx = int(pre_with_index[i][1])
            nice_images[i, 0, :, :] = generated_images[idx, 0, :, :]
        image = combine_images(nice_images)
    else:
        noise = np.zeros((BATCH_SIZE, 100))
        for i in range(BATCH_SIZE):
            noise[i, :] = np.random.uniform(-1, 1, 100)
        generated_images = generator.predict(noise, verbose=1)
        generated_images_tosave = generated_images.transpose((0, 3, 1, 2))
        image = combine_images(generated_images_tosave)
    image = image * 127.5 + 127.5
    Image.fromarray(image.astype(np.uint8)).save(p.join(output_folder, "generated_image.png"))


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str)
    parser.add_argument("--batch_size", type=int, default=128)
    parser.add_argument("--nice", dest="nice", action="store_true")
    parser.set_defaults(nice=False)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = get_args()
    if not p.exists(output_folder):
        os.makedirs(output_folder)
    if args.mode == "train":
        train(BATCH_SIZE=args.batch_size)
    elif args.mode == "generate":
        generate(BATCH_SIZE=args.batch_size, nice=args.nice)

# train(BATCH_SIZE=128)
