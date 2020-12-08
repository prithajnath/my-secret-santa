describe("User Sign In", () => {
  beforeAll(async () => {
    await page.goto("http://secret-santa-web:9000/login");
  });

  it("User can sign in and access their profile", async () => {
    // console.log(page);

    await page.goto("http://secret-santa-web:9000");
    await page.evaluate(async () => {
      const LoginLink = [...document.querySelectorAll("a")].find(
        (a) => a.href.slice(a.href.length - 6, a.href.length) === "/login"
      );

      await LoginLink.click();
    });

    await page.waitForNavigation();

    await page.evaluate(async () => {
      const username = document.querySelector("#username");
      username.value = "helenkeller";

      const password = document.querySelector("#password");
      password.value = "helloworld";

      const signInButton = document.querySelector("button.santa-button");
      await signInButton.click();
    });

    await page.waitForNavigation();

    await expect(
      page.evaluate(
        async () =>
          document.querySelector(".nav-link.dropdown-toggle").innerText
      )
    ).resolves.toMatch("@helenkeller");
  });
});
