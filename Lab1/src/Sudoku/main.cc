#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <pthread.h>
#include <vector>
#include <queue>
#include <mutex>
#include "sudoku.h"
using namespace std;

queue<string> puzzle_queue;
mutex queue_mutex;
mutex result_mutex;

struct ThreadStats
{
	int solved;
	int total;
};

int64_t now()
{
	struct timeval tv;
	gettimeofday(&tv, NULL);
	return tv.tv_sec * 1000000 + tv.tv_usec;
}

void *solve_thread(void *arg)
{
	bool (*solve)(int) = (bool (*)(int))arg; // 将void*转换为函数指针
	ThreadStats stats = {0, 0};
	string puzzle;

	while (true)
	{
		lock_guard<mutex> lock(queue_mutex); // 加锁
		if (puzzle_queue.empty()) { // 如果队列为空，则退出
			break;
		}
		puzzle = puzzle_queue.front(); // 获取队列中的第一个谜题
		puzzle_queue.pop(); // 移除队列中的第一个谜题
	}
	if (puzzle.length() >= N) {
		stats.total++;
		input(puzzle.c_str()); // 输入谜题
		init_cache(); // 初始化缓存
		
		if (solve(0)) {
			stats.solved++; // 如果解决成功，则增加解决的谜题数量
			if (!solved()) {
				assert(0); // 如果解决失败，则断言
			}
		} else {
			printf("No: %s", puzzle.c_str()); // 如果解决失败，则打印谜题
		}
	}

	// 合并结果
    {
        std::lock_guard<std::mutex> lock(result_mutex); // 加锁
        ThreadStats* result = new ThreadStats(stats); // 创建新的线程统计结果
        return (void*)result; // 返回结果
    }
}

int main(int argc, char *argv[])
{
	init_neighbors(); // 初始化邻居

	FILE *fp = fopen(argv[1], "r");
	char puzzle[128];
	int total_solved = 0;
	int total = 0;
	bool (*solve)(int) = solve_sudoku_basic;
	if (argv[2] != NULL)
		if (argv[2][0] == 'a')
			solve = solve_sudoku_min_arity;
		else if (argv[2][0] == 'c')
			solve = solve_sudoku_min_arity_cache;
		else if (argv[2][0] == 'd')
			solve = solve_sudoku_dancing_links;
	int64_t start = now();
	while (fgets(puzzle, sizeof puzzle, fp) != NULL)
	{
		if (strlen(puzzle) >= N)
		{
			++total;
			input(puzzle);
			init_cache();
			// if (solve_sudoku_min_arity_cache(0)) {
			// if (solve_sudoku_min_arity(0))
			// if (solve_sudoku_basic(0)) {
			if (solve(0))
			{
				++total_solved;
				if (!solved())
					assert(0);
			}
			else
			{
				printf("No: %s", puzzle);
			}
		}
	}
	int64_t end = now();
	double sec = (end - start) / 1000000.0;
	printf("%f sec %f ms each %d\n", sec, 1000 * sec / total, total_solved);

	return 0;
}
