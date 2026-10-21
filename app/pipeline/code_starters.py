"""
Starter code per language for the coding questions. Pure data, no imports from the app.

Python keeps each problem's own starter_code (it already parses the input). C++, Java and JavaScript get ONE generic
template each: it reads all of stdin and leaves the parsing to the student, because the 120 problems are stdin -> stdout
and are not rewritten per language. Every template prints nothing, so it can never pass a test by itself.
"""

FORMAT_NOTE = "Read the input exactly as the problem's input format describes, and print only the answer."

GENERIC_STARTERS = {
    "cpp": (
        "#include <iostream>\n"
        "#include <sstream>\n"
        "#include <string>\n"
        "#include <vector>\n"
        "#include <algorithm>\n"
        "using namespace std;\n"
        "\n"
        f"// {FORMAT_NOTE}\n"
        "// The whole of stdin is in `input`; split it into lines or tokens as you need.\n"
        "int main() {\n"
        "    stringstream buffer;\n"
        "    buffer << cin.rdbuf();\n"
        "    string input = buffer.str();\n"
        "\n"
        "    // Write your code here.\n"
        "\n"
        "    return 0;\n"
        "}\n"
    ),
    "java": (
        "import java.io.*;\n"
        "import java.util.*;\n"
        "\n"
        f"// {FORMAT_NOTE}\n"
        "// Keep the class name Main: the program runs as Main.java.\n"
        "public class Main {\n"
        "    public static void main(String[] args) throws IOException {\n"
        "        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in));\n"
        "        List<String> lines = new ArrayList<>();\n"
        "        String line;\n"
        "        while ((line = reader.readLine()) != null) {\n"
        "            lines.add(line);\n"
        "        }\n"
        "\n"
        "        // Write your code here.\n"
        "    }\n"
        "}\n"
    ),
    "javascript": (
        f"// {FORMAT_NOTE}\n"
        "// All of stdin, split into lines.\n"
        "const lines = require(\"fs\").readFileSync(0, \"utf8\").split(\"\\n\");\n"
        "\n"
        "// Write your code here.\n"
    ),
}


def starter_for(language, question):
    """The starter shown for `language`: the problem's own for Python, the generic template otherwise."""
    if language == "python":
        return question.get("starter_code", "")
    return GENERIC_STARTERS.get(language, "")
