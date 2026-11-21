package de.robv.android.xposed;

@SuppressWarnings("unused")
public class XC_MethodReplacement extends XC_MethodHook {
    public static XC_MethodReplacement returnConstant(final Object constantResult) {
        return null;
    }

    public static XC_MethodReplacement returnConstant(int priority, final Object constantResult) {
        return null;
    }

    protected Object replaceHookedMethod(MethodHookParam param) throws Throwable {
        return null;
    }
}
