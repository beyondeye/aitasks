// KtPsiOracle.java - the Kotlin compiler's own PSI (kotlin-compiler.jar from
// the kotlinc release) as a t1954_3 provider helper (`ktpsi`).
//
// Protocol (one long-lived JVM): each stdin line is {"src":"<base64>"} or
// {"version":true}; each stdout line answers it with
//   {"comments":[[start,end,kind,text_b64],...],   kind: line|block
//    "literals":[[start,end,"string",text_b64],...], whole string templates (interpolations included), char literals
//    "diags":[[at,reason],...],                     PsiErrorElement (and BAD_CHARACTER) offsets
//    "anchors":{"package":L,"importEnd":L}}         1-based lines; 0 = none, determined
// or {"unsupported":"..."} / {"error":"..."}. Every offset is a BYTE offset of
// the ORIGINAL source (t1954_3 position contract): the input is decoded as
// strict UTF-8 after any BOM; IntelliJ PSI requires "\n" line separators, so
// CRLF / CR are normalised and every PSI (UTF-16, normalised) index is mapped
// back through the original UTF-16 index to bytes. Each span's text is
// returned so the Go side checks src[start:end] == text.
//
// Built by oracle/ktpsi_build.sh into the git-ignored .ktpsi/; never executes
// the input (PSI parse only).

import com.intellij.openapi.util.Disposer;
import com.intellij.psi.PsiComment;
import com.intellij.psi.PsiElement;
import com.intellij.psi.PsiErrorElement;
import com.intellij.psi.PsiRecursiveElementWalkingVisitor;
import com.intellij.psi.tree.IElementType;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.jetbrains.kotlin.cli.common.messages.MessageCollector;
import org.jetbrains.kotlin.cli.jvm.compiler.EnvironmentConfigFiles;
import org.jetbrains.kotlin.cli.jvm.compiler.KotlinCoreEnvironment;
import org.jetbrains.kotlin.config.CommonConfigurationKeys;
import org.jetbrains.kotlin.config.CompilerConfiguration;
import org.jetbrains.kotlin.lexer.KtTokens;
import org.jetbrains.kotlin.psi.KtFile;
import org.jetbrains.kotlin.psi.KtImportList;
import org.jetbrains.kotlin.psi.KtPackageDirective;
import org.jetbrains.kotlin.psi.KtPsiFactory;
import org.jetbrains.kotlin.psi.KtStringTemplateExpression;

public class KtPsiOracle {
  static int templateDepth;
  static final Pattern SRC = Pattern.compile("\"src\"\\s*:\\s*\"([A-Za-z0-9+/=]*)\"");

  public static void main(String[] args) throws Exception {
    CompilerConfiguration cfg = new CompilerConfiguration();
    cfg.put(CommonConfigurationKeys.MESSAGE_COLLECTOR_KEY, MessageCollector.Companion.getNONE());
    org.jetbrains.kotlin.cli.FrontendConfigurationKeysKt.setExtensionsStorage(
        cfg, new org.jetbrains.kotlin.compiler.plugin.CompilerPluginRegistrar.ExtensionStorage());
    KotlinCoreEnvironment env = KotlinCoreEnvironment.createForProduction(
        Disposer.newDisposable(), cfg, EnvironmentConfigFiles.JVM_CONFIG_FILES);
    KtPsiFactory factory = new KtPsiFactory(env.getProject(), false);
    PrintStream out = new PrintStream(System.out, true, "UTF-8");
    BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
    for (String line; (line = in.readLine()) != null; ) {
      String resp;
      try {
        if (line.contains("\"version\"")) {
          resp = "{\"version\":\"" + org.jetbrains.kotlin.config.KotlinCompilerVersion.VERSION + "\"}";
        } else {
          Matcher m = SRC.matcher(line);
          if (!m.find()) throw new IllegalArgumentException("request without src");
          resp = analyze(factory, Base64.getDecoder().decode(m.group(1)));
        }
      } catch (Throwable e) {
        resp = "{\"error\":" + q(e.getClass().getSimpleName() + ": " + e.getMessage()) + "}";
      }
      out.println(resp);
    }
  }

  static String analyze(KtPsiFactory factory, byte[] src) {
    int bom = (src.length >= 3 && (src[0] & 0xff) == 0xEF && (src[1] & 0xff) == 0xBB && (src[2] & 0xff) == 0xBF) ? 3 : 0;
    String text;
    try {
      text = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
          .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(src, bom, src.length - bom)).toString();
    } catch (CharacterCodingException e) {
      return "{\"unsupported\":\"UTF-8-input\"}";
    }
    // UTF-16 index of the original text -> byte offset of the original source.
    int[] byteAt = new int[text.length() + 1];
    int b = bom;
    for (int i = 0; i < text.length(); i++) {
      byteAt[i] = b;
      char c = text.charAt(i);
      if (Character.isHighSurrogate(c) && i + 1 < text.length() && Character.isLowSurrogate(text.charAt(i + 1))) {
        byteAt[i + 1] = -1; // inside a surrogate pair: no byte offset
        b += 4;
        i++;
        continue;
      }
      b += c < 0x80 ? 1 : c < 0x800 ? 2 : 3;
    }
    byteAt[text.length()] = b;
    // PSI needs "\n" separators: normalise and remember each index's origin.
    StringBuilder norm = new StringBuilder(text.length());
    List<Integer> orig = new ArrayList<>(text.length() + 1);
    for (int i = 0; i < text.length(); i++) {
      char c = text.charAt(i);
      if (c == '\r') {
        orig.add(i);
        norm.append('\n');
        if (i + 1 < text.length() && text.charAt(i + 1) == '\n') i++;
        continue;
      }
      orig.add(i);
      norm.append(c);
    }
    orig.add(text.length());
    // o[normalised index] = original UTF-16 index (one extra entry: the end).
    final int[] o = orig.stream().mapToInt(Integer::intValue).toArray();
    KtFile file = factory.createFile("input.kt", norm.toString());
    StringBuilder comments = new StringBuilder(), literals = new StringBuilder(), diags = new StringBuilder();
    templateDepth = 0;
    file.accept(new PsiRecursiveElementWalkingVisitor() {
      @Override public void visitElement(PsiElement e) {
        if (e instanceof PsiComment) {
          IElementType t = ((PsiComment) e).getTokenType();
          String kind = (t == KtTokens.EOL_COMMENT || t == KtTokens.SHEBANG_COMMENT) ? "line" : "block";
          span(comments, e.getTextRange().getStartOffset(), e.getTextRange().getEndOffset(), kind, src, o, byteAt);
          return;
        }
        if (e instanceof KtStringTemplateExpression) {
          // only the outermost template is a span (interpolations and nested
          // templates are inside its range), but the walk still descends:
          // a PsiErrorElement for a missing closing quote lives INSIDE it
          if (templateDepth++ == 0) {
            span(literals, e.getTextRange().getStartOffset(), e.getTextRange().getEndOffset(), "string", src, o, byteAt);
          }
        }
        if (e.getNode() != null && e.getNode().getElementType() == KtTokens.CHARACTER_LITERAL) {
          span(literals, e.getTextRange().getStartOffset(), e.getTextRange().getEndOffset(), "string", src, o, byteAt);
        }
        if (e instanceof PsiErrorElement) {
          int at = byteOf(e.getTextRange().getStartOffset(), o, byteAt);
          if (diags.length() > 0) diags.append(',');
          diags.append('[').append(at).append(',').append(q(((PsiErrorElement) e).getErrorDescription())).append(']');
        }
        if (e.getNode() != null && e.getNode().getElementType() == com.intellij.psi.TokenType.BAD_CHARACTER) {
          int at = byteOf(e.getTextRange().getStartOffset(), o, byteAt);
          if (diags.length() > 0) diags.append(',');
          diags.append('[').append(at).append(',').append(q("bad character")).append(']');
        }
        super.visitElement(e);
      }

      @Override protected void elementFinished(PsiElement e) {
        if (e instanceof KtStringTemplateExpression) templateDepth--;
      }
    });
    int pkg = 0, imp = 0;
    KtPackageDirective pd = file.getPackageDirective();
    if (pd != null && pd.getTextLength() > 0) pkg = lineOf(norm, pd.getTextRange().getEndOffset());
    KtImportList il = file.getImportList();
    if (il != null && !il.getImports().isEmpty()) imp = lineOf(norm, il.getTextRange().getEndOffset());
    return "{\"comments\":[" + comments + "],\"literals\":[" + literals + "],\"diags\":[" + diags
        + "],\"anchors\":{\"package\":" + pkg + ",\"importEnd\":" + imp + "}}";
  }

  static int byteOf(int normIdx, int[] o, int[] byteAt) {
    int b = byteAt[o[normIdx]];
    if (b < 0) throw new IllegalStateException("offset inside a surrogate pair");
    return b;
  }

  static void span(StringBuilder sb, int s, int e, String kind, byte[] src, int[] o, int[] byteAt) {
    int bs = byteOf(s, o, byteAt);
    // the end: o[e] is the original index of the character after the span
    // (o has an entry for the end of the text), so CRLF and surrogate pairs
    // inside the span are covered whole
    int be = byteOf(e, o, byteAt);
    if (sb.length() > 0) sb.append(',');
    byte[] t = java.util.Arrays.copyOfRange(src, bs, be);
    sb.append('[').append(bs).append(',').append(be).append(',').append(q(kind)).append(',')
        .append(q(Base64.getEncoder().encodeToString(t))).append(']');
  }

  static int lineOf(CharSequence s, int idx) {
    int line = 1;
    for (int i = 0; i < idx && i < s.length(); i++) if (s.charAt(i) == '\n') line++;
    return line;
  }

  static String q(String s) {
    if (s == null) return "null";
    StringBuilder b = new StringBuilder("\"");
    for (char c : s.toCharArray()) {
      if (c == '"' || c == '\\') b.append('\\').append(c);
      else if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
      else b.append(c);
    }
    return b.append('"').toString();
  }
}
