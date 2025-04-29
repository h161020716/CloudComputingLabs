#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <time.h>
#include <pthread.h>
#include <string.h>
#include <unistd.h>
#include <string.h>
#include <vector>
#include <getopt.h>
#include "http.h"
#include "get.h"
#include "post.h"
#include <sys/stat.h>
#include <assert.h>
#include <fcntl.h>

using namespace std;

#define MAXREQ 256
#define N 8192

//监听客户端的线程，与客户端建立连接，读取客户端的请求，处理请求
void* server(void* args) {
  
  int* serversockfdAddr = (int*)args;
  int server_sockfd = *serversockfdAddr;

  while(1)
  {
    int consockfd;
    socklen_t sin_size = sizeof(struct sockaddr_in);
    struct sockaddr_in remote_addr;
    if((consockfd = accept(server_sockfd,(struct sockaddr *)&remote_addr,&sin_size))<0)
    {
      perror("Error: accept");
      continue;
    }
    char *readbuffer = (char *)malloc(N+1);
    int n;
    struct http_request *request = (struct http_request *)malloc(sizeof(struct http_request));
    n=read(consockfd,readbuffer,N);
    if(n<=0) continue;


    char* start_str = readbuffer;
    char* end_str;
    while((end_str = strstr(start_str,"\r\n\r\n")))
    {
      size_t len = end_str - start_str + 4;
      char* request_buf = (char *)malloc(len+1);
      memcpy(request_buf,start_str,len);
      request_buf[len] = '\0';
      if(strstr(request_buf,"POST"))
      {
        char* content_l = strstr(readbuffer,"Content-Length: ");
        int cont_l=0;
        sscanf(content_l,"Content-Length: %d",&cont_l);
        len=len+cont_l+4;
        char *request_b = (char *)malloc(len+1);
        memcpy(request_b,start_str,len);
        request  = http_request_parse(request_b);
        post_method(request,consockfd);

        free(request_b);
      }
      else{
        request = http_request_parse(request_buf);
        get_method(request,consockfd);
      }
      free(request_buf);
      
      start_str = end_str +4;
    }
    close(consockfd);
    free(request);
    free(readbuffer);
  }
  return NULL;
}

//创建套接字， 绑定端口 ， 监听端口， 创建线程， 等待所有进程结束
int main(int argc, char *argv[])
{
  int option;
  char *ip = "127.0.0.1";
  int port = 8888;
  int threads = 8;
  char *proxy_ip = "127.0.0.1";
  
  struct option long_options[] = {
      {"ip", required_argument, 0, 'i'},
      {"port", required_argument, 0, 'p'},
      {"threads", required_argument, 0, 't'},
      {"proxy_ip", required_argument, 0, 'x'},
      {0, 0, 0, 0}};

  while ((option = getopt_long(argc, argv, "i:p:t:", long_options, NULL)) != -1)
  {
    switch (option)
    {
      case 'i':
        ip = optarg;
        break;
      case 'p':
        port = atoi(optarg);
        break;
      case 't':
        threads = atoi(optarg);
        break;
      case 'x':
        proxy_ip = optarg;
        break;
      default:
        return 1;
        }
    }
   
  //待补全 
  struct sockaddr_in my_addr;
  my_addr.sin_family = AF_INET;
  my_addr.sin_addr.s_addr = inet_addr(ip);
  my_addr.sin_port = htons(port);

  //创建套接字
  int server_sockfd;
  if((server_sockfd = socket(AF_INET,SOCK_STREAM,0))<0)
  {
    perror("Error: socket");
    return 1;
  }
  //配置
  int on =1;
  if((setsockopt(server_sockfd,SOL_SOCKET,SO_REUSEADDR,&on,sizeof(on)))<0)
  {
    perror("Error: setsockopt");
    return 1;
  }
  //绑定
  if(bind(server_sockfd,(struct sockaddr *)&my_addr,sizeof(my_addr))<0)
  {
    perror("Error: bind");
    return 1;
  }
  //监听
  if((listen(server_sockfd,5))<0)
  {
    perror("Error: listen");
    return 1;
  }
  //创建线程处理连接
  vector<pthread_t> threadl(threads);
  for(int i=0;i<threads;++i)
  {
    if(pthread_create(&threadl[i],NULL,server,&server_sockfd)!=0)
    {
      perror("Error: pthread_create");
      exit(1);
    }
  }
  //等待所有线程结束
  for(int i=0;i<threads;++i)
  {
    pthread_join(threadl[i],NULL);
  }
  close(server_sockfd);



  return 0;
}
