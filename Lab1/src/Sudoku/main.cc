#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <string>
#include "sudoku.h"
#include <thread>
#include <iostream>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <atomic>
using namespace std;

mutex input_mtx;
mutex work_mtx;
condition_variable cv,cv1;
queue<string> input_queue;
vector<pair<string, bool>> puzzle_queue;
int current_index = 0;
int output_index = 0;
bool stop =false;

int64_t now()
{
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return tv.tv_sec * 1000000 + tv.tv_usec;
}

void input_thread()
{
  while (!stop) { 
    string filename;
    cin >> filename;
    input_mtx.lock();
    input_queue.push(filename);
    input_mtx.unlock();  
  } 
}

void read_thread()
{
  while (!stop) {
    string filename;
    input_mtx.lock();
    if (!input_queue.empty()) {
      filename = input_queue.front();
      input_queue.pop();
    }
    input_mtx.unlock();
    if (!filename.empty()) {
      FILE *fp = fopen(filename.c_str(), "r");
      if (fp) {
        //cout<<"read_thread: "<<filename<<endl;
        char puzzle[128];
        while (fgets(puzzle, sizeof(puzzle), fp) != NULL) {
          if (strlen(puzzle) >= N) {
            work_mtx.lock();
            puzzle_queue.push_back({string(puzzle), 0});
            cv.notify_one();
            work_mtx.unlock();
          }
        }
      }
      fclose(fp);
    }
  }
}

void solve_thread()
{
  while (!stop) {
    vector<pair<string, bool>> work_queue;
    unsigned int start_index;
    unique_lock<mutex> lock(work_mtx); 
    cv.wait(lock,[]{return current_index < puzzle_queue.size();});
    //cout<<"solve_thread:"<<endl;
    start_index = current_index;  
    for(int i = 0; i < 10 && current_index < puzzle_queue.size(); i++) {
      work_queue.push_back(puzzle_queue[current_index]);
      ++current_index;
    }
    lock.unlock();
    if(work_queue.empty())
      break;
    for(size_t i = 0; i < work_queue.size(); i++) 
    {
      string puzzle = work_queue[i].first;
      if(puzzle.size() >= N) {
        int board[N];
        for(int i = 0; i < N; i++) {
          board[i] = puzzle[i] - '0';
          assert(board[i] >= 0 && board[i] <= 9);
        }
        solve_sudoku_dancing_links(board);
        string result;
        for(int j = 0; j < N; j++) {
          char c = board[j] + '0';
          result += c;
        }
        //cout<<result<<endl;
        work_queue[i] = {result, 1};
      }
    }
    work_mtx.lock();
    for(size_t i = 0; i < work_queue.size(); i++)
      puzzle_queue[start_index + i] = work_queue[i];
    //cout<<"solve_thread:1"<<endl;
    cv1.notify_one();
    work_mtx.unlock();
    
    
  }
}

void output_thread()
{
  while (!stop) {
    //cout<<"output_thread:"<<endl;
    unique_lock<mutex> lock(work_mtx);
    cv1.wait(lock,[]{return output_index < puzzle_queue.size() && puzzle_queue[output_index].second;});
    //cout<<"output_thread1:"<<endl;
    while (output_index < puzzle_queue.size() && puzzle_queue[output_index].second) {
      string result = puzzle_queue[output_index].first;
      printf("%s\n", result.c_str());
      output_index++;
    }
    lock.unlock();
  }
}

int main(int argc, char *argv[])
{
  
  int num_cores = thread::hardware_concurrency();  
  if (num_cores == 0)  
      num_cores = 1;  
 // cout<<num_cores<<endl;
  vector<thread> threads;  

  thread t0(input_thread);
  thread t1(read_thread);  
  thread t2(output_thread);
  for (int i = 0; i < num_cores; i++)  
      threads.emplace_back(solve_thread);  

  for (auto &t : threads)  
      t.join();
  t0.join();
  t1.join();
  t2.join();
  return 0;
}