# Build the solver sidecar.
#
#   make            -> build/solverd
#   make run        -> build and start it on run/solverd.sock
#   make clean
#
# Plain make rather than CMake: cmake is not on PATH on the reference machine,
# and this is one binary from eight translation units. The core sources are
# shared with the Python extension in ../native — compiled here, not duplicated.

CXX      ?= c++
CXXFLAGS ?= -std=c++20 -O3 -Wall -Wextra -pthread
INCLUDES  = -I../native/include
LDFLAGS   = -pthread

CORE_SRC = $(wildcard ../native/src/*.cpp)
SRC      = main.cpp $(CORE_SRC)
OBJ      = $(patsubst %.cpp,build/%.o,$(notdir $(SRC)))
BIN      = build/solverd

VPATH = ../native/src

.PHONY: all run clean

all: $(BIN)

$(BIN): $(OBJ)
	$(CXX) $(CXXFLAGS) $(OBJ) -o $@ $(LDFLAGS)

build/%.o: %.cpp | build
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

build:
	mkdir -p build

run: $(BIN)
	cd .. && solverd/build/solverd --socket run/solverd.sock --banks app/data/banks

clean:
	rm -rf build
