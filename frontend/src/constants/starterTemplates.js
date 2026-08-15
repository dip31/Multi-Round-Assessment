export const DEFAULT_STARTER = '// Write your solution here\n';

// stdin/stdout oriented skeletons per language. Judge0 always compiles Java to
// Main.java and runs `java Main`, so the Java template must define `Main`.
export const STARTER_TEMPLATES = {
  python: `import sys

def main():
    data = sys.stdin.read().split()
    # TODO: implement your solution here, then print the result
    print('')

if __name__ == "__main__":
    main()
`,
  javascript: `const readline = require("readline");

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

const lines = [];
rl.on("line", (line) => lines.push(line));

rl.on("close", () => {
  // TODO: implement your solution here, then print the result
});
`,
  java: `import java.util.*;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        // TODO: implement your solution here, then print the result
        sc.close();
    }
}
`,
  cpp: `#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    // TODO: implement your solution here, then print the result
    return 0;
}
`,
};
