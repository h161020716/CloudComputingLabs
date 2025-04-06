CXX = g++  
CXXFLAGS += -std=c++11 -pthread -o -ggdb -DDEBUG -Wall -Wextra  

# 默认目标  
all: sudoku_solve  

# 定义目标和依赖关系  
sudoku_solve: main.cc sudoku_dancing_links.cc  sudoku.h
	$(CXX) $(CXXFLAGS) -o $@ $^   

# 模式规则，用于编译源文件为目标文件  
%.o: %.cc  
	$(CXX) $(CXXFLAGS) -c $<  # 编译源文件为对象文件  

# 清理构建的文件  
clean:  
	rm -f sudoku_solve *.o  