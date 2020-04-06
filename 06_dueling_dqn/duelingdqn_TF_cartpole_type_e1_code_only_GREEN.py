import tensorflow as tf
import gym
import numpy as np
import random
from collections import deque
from typing import List

env = gym.make('CartPole-v0')
INPUT_SIZE = env.observation_space.shape[0]
OUTPUT_SIZE = env.action_space.n
Gamma = 0.99
N_EPISODES = 5000
N_train_result_replay = 20
TARGET_UPDATE_CYCLE = 10
SIZE_R_M = 50000
MINIBATCH = 64

rlist=[]

MIN_E = 0.0
EPSILON_DECAYING_EPISODE = N_EPISODES * 0.01

class DuelingDQN:

    def __init__(self, session: tf.Session, INPUT_SIZE: int, OUTPUT_SIZE: int, name: str="main") -> None:
        self.session = session
        self.INPUT_SIZE = INPUT_SIZE
        self.OUTPUT_SIZE = OUTPUT_SIZE
        self.net_name = name

        self._BUILD_NETWORK()

    def _BUILD_NETWORK(self, H_SIZE_01=200, H_SIZE_15_state = 200, H_SIZE_15_action = 200, Alpha=0.001) -> None:
        """DQN Network architecture (simple MLP)

        Args:
            h_size (int, optional): Hidden layer dimension
            Alpha (float, optional): Learning rate
        """
        # Hidden Layer 01 Size  : H_SIZE_01 = 200

        with tf.variable_scope(self.net_name):
            self._X = tf.placeholder(dtype=tf.float32, shape= [None, self.INPUT_SIZE], name="input_X")
            self._Y = tf.placeholder(dtype=tf.float32, shape= [None, self.OUTPUT_SIZE], name="output_Y")
            self.dropout = tf.placeholder(dtype=tf.float32)
            H_SIZE_16_state = self.OUTPUT_SIZE
            H_SIZE_16_action = self.OUTPUT_SIZE
            
            net_0 = self._X

            net_1 = tf.layers.dense(net_0, H_SIZE_01, activation=tf.nn.relu)
            net_15_state = tf.layers.dense(net_1, H_SIZE_15_state, activation=tf.nn.relu)
            net_15_action = tf.layers.dense(net_1, H_SIZE_15_action, activation=tf.nn.relu)
            
            net_16_state = tf.layers.dense(net_15_state, H_SIZE_16_state)
            net_16_action = tf.layers.dense(net_15_action, H_SIZE_16_action)
            
            net16_advantage = tf.subtract(net_16_action, tf.reduce_mean(net_16_action))
            
            Q_prediction = tf.add(net_16_state, net16_advantage)
            
            self._Qpred = Q_prediction

            self._LossValue = tf.losses.mean_squared_error(self._Y, self._Qpred)

            optimizer = tf.train.AdamOptimizer(learning_rate=Alpha)
            self._train = optimizer.minimize(self._LossValue)

    def predict(self, state: np.ndarray) -> np.ndarray:
        x = np.reshape(state, [-1, self.INPUT_SIZE])
        return self.session.run(self._Qpred, feed_dict={self._X: x})

    def update(self, x_stack: np.ndarray, y_stack: np.ndarray) -> list:
        feed = {
            self._X: x_stack,
            self._Y: y_stack
        }
        return self.session.run([self._LossValue, self._train], feed)

def Train_Play(mainDQN):
    state = env.reset()
    total_reward = 0

    while True:

        env.render()
        action = np.argmax(mainDQN.predict(state))
        state, reward, done, _ = env.step(action)
        total_reward += reward

        if done:
            print("Total score: {}".format(total_reward))
            break

def annealing_epsilon(episode: int, min_e: float, max_e: float, target_episode: int) -> float:

    slope = (min_e - max_e) / (target_episode)
    intercept = max_e

    return max(min_e, slope * episode + intercept)

def Copy_Weights(*, dest_scope_name: str, src_scope_name: str) -> List[tf.Operation]:
    op_holder = []

    src_vars = tf.get_collection(
        tf.GraphKeys.TRAINABLE_VARIABLES, scope=src_scope_name)
    dest_vars = tf.get_collection(
        tf.GraphKeys.TRAINABLE_VARIABLES, scope=dest_scope_name)

    for src_var, dest_var in zip(src_vars, dest_vars):
        op_holder.append(dest_var.assign(src_var.value()))

    return op_holder
                 
def train_minibatch(mainDQN, targetDQN, train_batch):
    x_stack = np.empty(0).reshape(0, mainDQN.INPUT_SIZE)
    y_stack = np.empty(0).reshape(0, mainDQN.OUTPUT_SIZE)

    # Get stored information from the buffer
    for state, action, reward, nextstate, done in train_batch:
        Q_Global = mainDQN.predict(state)
        
        if done:
            Q_Global[0,action] = reward
            
        else:
            Q_Global[0,action] = reward + Gamma * np.max(targetDQN.predict(nextstate))

        y_stack = np.vstack([y_stack, Q_Global])
        x_stack = np.vstack([x_stack, state])
    
    return mainDQN.update(x_stack, y_stack)

def main():
    
    last_N_game_reward = deque(maxlen=100)
    last_N_game_reward.append(0)
    replay_buffer = deque(maxlen=SIZE_R_M)

    with tf.Session() as sess:
        mainDQN = DuelingDQN(sess, INPUT_SIZE, OUTPUT_SIZE, name="main")
        targetDQN = DuelingDQN(sess, INPUT_SIZE, OUTPUT_SIZE, name="target")
        init = tf.global_variables_initializer()
        sess.run(init)

        copy_ops = Copy_Weights(dest_scope_name="target",
                                    src_scope_name="main")
        sess.run(copy_ops)

        for episode in range(N_EPISODES):        
            state = env.reset()
            e = annealing_epsilon(episode, MIN_E, 1.0, EPSILON_DECAYING_EPISODE)
            rall = 0
            done = False
            count = 0

            while not done and count < 10000 :
                count += 1
                if e > np.random.rand(1):
                    action = env.action_space.sample()
                else:
                    action = np.argmax(mainDQN.predict(state))

                nextstate, reward, done, _ = env.step(action)

                if done:
                    reward = -100

                replay_buffer.append((state, action, reward, nextstate, done))

                if len(replay_buffer) > SIZE_R_M:
                    replay_buffer.popleft()
                    
                state = nextstate
                if count > 10000:
                    break

            if count > 10000:
                pass

            if episode % TARGET_UPDATE_CYCLE ==0:
                for _ in range (MINIBATCH):
                    minibatch = random.sample(replay_buffer, 10)
                    LossValue,_ = train_minibatch(mainDQN,targetDQN, minibatch)
                print("LossValue : ",LossValue)
                sess.run(copy_ops)
                    
                print("Episode {:>5} reward:{:>5} recent N Game reward:{:>5.2f} memory length:{:>5}"
                      .format(episode, count, np.mean(last_N_game_reward),len(replay_buffer)))
            
            # Train_Play(mainDQN)
            last_N_game_reward.append(count)

            if len(last_N_game_reward) == last_N_game_reward.maxlen:
                avg_reward = np.mean(last_N_game_reward)

                if avg_reward > 199.0:
                    print("Game Cleared within {:>5} episodes with avg reward {:>5.2f}".format(episode, avg_reward))
                    break

        for episode in range(N_train_result_replay):
            
            state = env.reset()
            rall = 0
            done = False
            count = 0
            
            while not done :
                env.render()
                count += 1
                Q_Global = mainDQN.predict(state)
                action = np.argmax(Q_Global)
                state, reward, done, _ = env.step(action)
                rall += reward

            rlist.append(rall)
            print("Episode : {:>5} steps : {:>5} r={:>5}. averge reward : {:>5.2f}".format(episode, count, rall, np.mean(rlist)))

if __name__ == "__main__":
    main()